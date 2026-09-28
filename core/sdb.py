"""Bathymetry workflow on numpy arrays, independent of QGIS so it can be tested.

Methods:
  stumpf_bg  Stumpf et al. (2003), ln(n*Rblue)/ln(n*Rgreen), linear fit
  stumpf_br  same with blue/red
  stumpf_sw  blue/red in very shallow water, blue/green deeper, blended (switching)
  lyzenga    Lyzenga (1978, 1985): depth = a0 + sum a_i ln(R_i - Rinf_i)
  rf         Random Forest (scikit-learn) on ln(R) of blue, green, red and both pSDB

Calibration/validation: ONE split of all the points (spatial blocks or random).
Each method is fitted on its own valid calibration points and evaluated twice:
  - common: validation points valid for every selected method (same sample)
  - own:    every validation point valid for that method (its full sample)
The common sample can be shallower than the own ones (a method that loses the
deep points removes them for everybody), so both are reported with the depth
distribution of each sample.

Optical depth limit: for the Stumpf ratios the calibration can be cut at the
depth where pSDB stops growing (see saturation.py). Pixels predicted deeper than
the limit are flagged in the trust raster.
"""
import numpy as np

from . import saturation, stumpf, validation

NODATA = -9999.0

METHODS = {
    "stumpf_bg": "Stumpf blue/green",
    "stumpf_br": "Stumpf blue/red",
    "stumpf_sw": "Stumpf switching (blue/red to blue/green)",
    "lyzenga": "Lyzenga multiband",
    "rf": "Random Forest",
}


# ---------------------------------------------------------------- sampling
def pixel_index(gt, xs, ys):
    cols = np.floor((np.asarray(xs) - gt[0]) / gt[1]).astype(np.int64)
    rows = np.floor((np.asarray(ys) - gt[3]) / gt[5]).astype(np.int64)
    return rows, cols


def sample(arr, rows, cols, window=1):
    """Value at each (row, col); window=3 gives the 3x3 median (NaN-aware)."""
    h, w = arr.shape
    out = np.full(len(rows), np.nan)
    half = window // 2
    for i, (r, c) in enumerate(zip(rows, cols)):
        if r < 0 or c < 0 or r >= h or c >= w:
            continue
        if window == 1:
            out[i] = arr[r, c]
        else:
            block = arr[max(0, r - half):r + half + 1, max(0, c - half):c + half + 1]
            if np.isfinite(block).any():
                out[i] = np.nanmedian(block)
    return out


def aggregate_per_pixel(rows, cols, xs, ys, depths):
    keys = rows.astype(np.int64) * 1_000_003 + cols.astype(np.int64)
    uniq, inv = np.unique(keys, return_inverse=True)
    cnt = np.bincount(inv)

    def mean(v):
        return np.bincount(inv, weights=np.asarray(v, dtype=np.float64)) / cnt

    first = np.zeros(len(uniq), dtype=np.int64)
    first[inv[::-1]] = np.arange(len(inv))[::-1]
    return rows[first], cols[first], mean(xs), mean(ys), mean(depths), cnt


# ---------------------------------------------------------------- features
def _log_minus(r, rinf):
    with np.errstate(invalid="ignore", divide="ignore"):
        x = np.log(np.asarray(r, dtype=np.float64) - rinf)
    x[~np.isfinite(x)] = np.nan
    return x


def base_features(bands, n_const, r_inf, lyzenga_bands):
    """Every feature image any method may need, computed once."""
    f = {
        "pSDB_bg": stumpf.log_ratio(bands["blue"], bands["green"], n_const),
        "pSDB_br": stumpf.log_ratio(bands["blue"], bands["red"], n_const),
    }
    for b in ("blue", "green", "red"):
        f[f"lnR_{b}"] = _log_minus(bands[b], 0.0)
    for b in lyzenga_bands:
        f[f"X_{b}"] = _log_minus(bands[b], r_inf.get(b, 0.0))
    return f


def feature_names(method, lyzenga_bands=("blue", "green")):
    return {
        "stumpf_bg": ["pSDB_bg"],
        "stumpf_br": ["pSDB_br"],
        "stumpf_sw": ["pSDB_bg"],  # blue/green must exist; blue/red is optional
        "lyzenga": [f"X_{b}" for b in lyzenga_bands],
        "rf": ["lnR_blue", "lnR_green", "lnR_red", "pSDB_bg", "pSDB_br"],
    }[method]


# ---------------------------------------------------------------- models
def _rf_model(n_trees, seed):
    try:
        from sklearn.ensemble import RandomForestRegressor
    except ImportError:
        return None
    return RandomForestRegressor(n_estimators=n_trees, min_samples_leaf=2,
                                 random_state=seed, n_jobs=-1)


def rf_mean_sd(model, X, chunk=50_000):
    """Mean and standard deviation of the individual tree predictions.

    The mean is the forest prediction. The spread between trees is a relative
    measure of disagreement, not a calibrated prediction interval: its coverage
    is checked against the validation points in the report.
    """
    X = np.asarray(X)
    mean = np.empty(len(X))
    sd = np.empty(len(X))
    trees = model.estimators_
    for s0 in range(0, len(X), chunk):
        part = X[s0:s0 + chunk]
        acc = np.zeros(len(part))
        acc2 = np.zeros(len(part))
        for t in trees:
            p = t.predict(part)
            acc += p
            acc2 += p * p
        m = acc / len(trees)
        mean[s0:s0 + chunk] = m
        sd[s0:s0 + chunk] = np.sqrt(np.maximum(acc2 / len(trees) - m * m, 0.0))
    return mean, sd


def coverage(obs, pred, sd):
    """Fraction of points whose error is within 1 and 2 standard deviations."""
    obs, pred, sd = (np.asarray(v, dtype=np.float64) for v in (obs, pred, sd))
    ok = np.isfinite(obs) & np.isfinite(pred) & np.isfinite(sd)
    if not ok.any():
        return {"n": 0, "within1": np.nan, "within2": np.nan, "mean_sd": np.nan}
    err = np.abs(pred[ok] - obs[ok])
    return {"n": int(ok.sum()), "within1": float(np.mean(err <= sd[ok])),
            "within2": float(np.mean(err <= 2 * sd[ok])), "mean_sd": float(np.mean(sd[ok]))}


def _fit_linear(X, y):
    A = np.column_stack([np.ones(len(y)), X])
    if len(y) <= A.shape[1]:
        raise ValueError(f"Not enough calibration points ({len(y)}) for {A.shape[1]} coefficients.")
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef


def _predict_linear(coef, feats):
    out = np.full(feats[0].shape, coef[0], dtype=np.float64)
    for c, f in zip(coef[1:], feats):
        out = out + c * f
    return out


def _fit_stumpf(name, F_pts, F_img, depths, cal, use_saturation, warnings, label):
    """Linear Stumpf fit with optional depth limit. Returns a model dict."""
    p = F_pts[name]
    if use_saturation:
        sat = saturation.detect_saturation(depths[cal], p[cal])
    else:
        sat = {"saturated": False, "z_lim": float(depths[cal].max()), "reason": "detection off",
               "slope_before": np.nan, "slope_after": np.nan, "n": int(cal.sum())}
    fit_pts = cal & (depths <= sat["z_lim"]) if sat["saturated"] else cal
    if fit_pts.sum() < 5:
        warnings.append(f"{label}: only {int(fit_pts.sum())} calibration points below the depth limit; "
                        "fitted on all calibration points instead.")
        fit_pts = cal
        sat = dict(sat, saturated=False, z_lim=float(depths[cal].max()), reason="too few points below limit")
    coef = _fit_linear(p[fit_pts][:, None], depths[fit_pts])
    if coef[1] <= 0:
        warnings.append(f"{label}: slope is negative or zero ({coef[1]:.3f}). Depth should grow with "
                        "pSDB; the fit is not physically sensible.")
    if sat["saturated"]:
        warnings.append(f"{label}: pSDB stops growing at about {sat['z_lim']:.1f} m; calibrated only "
                        "above that depth and deeper predictions flagged in the trust raster.")
    return {"coef": coef, "sat": sat, "fit_pts": fit_pts,
            "pred_pts": coef[0] + coef[1] * p,
            "pred_img": coef[0] + coef[1] * F_img[name],
            "fmin": [float(np.nanmin(p[fit_pts]))], "fmax": [float(np.nanmax(p[fit_pts]))],
            "zmin": float(depths[fit_pts].min()), "zmax": float(sat["z_lim"])}


def _distribution(d):
    d = np.asarray(d, dtype=np.float64)
    d = d[np.isfinite(d)]
    if not len(d):
        return {"n": 0, "min": np.nan, "median": np.nan, "max": np.nan}
    return {"n": int(len(d)), "min": float(d.min()), "median": float(np.median(d)), "max": float(d.max())}


# ---------------------------------------------------------------- main
def run(bands, gt, xs, ys, depths, methods=("stumpf_bg",), n_const=1000.0,
        r_inf=None, window=1, aggregate=True, split="blocks", block_size=500.0,
        val_fraction=0.3, seed=42, bin_edges=(0, 2, 5, 10, 15, 20), rf_trees=300,
        lyzenga_bands=("blue", "green"), saturation_limit=True, switch_range=None):
    """bands: dict with 'blue', 'green', 'red' 2D arrays (NaN = nodata).

    xs, ys: point coordinates in the raster CRS. depths: positive down, already
    corrected to the water level at acquisition time.
    r_inf: dict of deep-water reflectance per band for Lyzenga (None = 0).
    switch_range: (start, end) in m for stumpf_sw, or None for automatic.
    Returns (results, depth_rasters, trust_rasters, points_table, warnings).
    """
    warnings = []
    r_inf = r_inf or {}
    methods = list(methods)
    lyzenga_bands = tuple(lyzenga_bands)
    if "lyzenga" in methods and not lyzenga_bands:
        raise ValueError("Lyzenga needs at least one band.")
    if "lyzenga" in methods and not r_inf:
        warnings.append("Lyzenga without a deep-water sample: R_inf = 0, so it uses ln(R). "
                        "This is a simplification; give a deep-water polygon if you can.")
    if "rf" in methods and _rf_model(10, seed) is None:
        warnings.append("Random Forest skipped: scikit-learn is not installed in the QGIS Python.")
        methods.remove("rf")
    if not methods:
        return [], {}, {}, {}, warnings

    # ---- points
    xs, ys, depths = (np.asarray(v, dtype=np.float64) for v in (xs, ys, depths))
    rows, cols = pixel_index(gt, xs, ys)
    h, w = bands["blue"].shape
    inside = (rows >= 0) & (cols >= 0) & (rows < h) & (cols < w) & np.isfinite(depths)
    if (~inside).sum():
        warnings.append(f"{int((~inside).sum())} points fall outside the raster or have no depth; ignored.")
    rows, cols, xs, ys, depths = rows[inside], cols[inside], xs[inside], ys[inside], depths[inside]
    if aggregate:
        n_before = len(depths)
        rows, cols, xs, ys, depths, _ = aggregate_per_pixel(rows, cols, xs, ys, depths)
        if len(depths) < n_before:
            warnings.append(f"{n_before} points averaged into {len(depths)} pixels.")
    if (depths < 0).any():
        warnings.append(f"{int((depths < 0).sum())} points have negative depth (above the water "
                        "surface after the tide correction). Check the sign convention.")
    npts = len(depths)
    table = {"x": xs, "y": ys, "depth": depths}
    if npts < 10:
        warnings.append(f"Only {npts} usable points. Nothing fitted.")
        return [], {}, {}, table, warnings

    # ---- features at the points
    F_img = base_features(bands, n_const, r_inf, lyzenga_bands)
    F_pts = {k: sample(v, rows, cols, window) for k, v in F_img.items()}
    ok_by = {m: np.all([np.isfinite(F_pts[f]) for f in feature_names(m, lyzenga_bands)], axis=0)
             for m in methods}
    common = np.all([ok_by[m] for m in methods], axis=0)
    lost_alone = {m: int((~ok_by[m]).sum()) for m in methods}
    if (~common).sum():
        detail = ", ".join(f"{METHODS[m]} {lost_alone[m]}" for m in methods)
        warnings.append(f"{int((~common).sum())} of {npts} points are not valid for every method. "
                        f"Points each method loses: {detail}. Metrics are given on the common points "
                        "and on each method's own points.")

    # ---- one split for everybody
    if split == "blocks":
        val, nb = validation.split_blocks(xs, ys, block_size, val_fraction, seed)
        split_txt = f"spatial blocks of {block_size:g} m ({nb} blocks)"
    else:
        val = validation.split_random(npts, val_fraction, seed)
        split_txt = "random"
    table["set"] = np.where(val, "val", "cal").astype(object)
    common_val = common & val
    if common_val.sum() < 30:
        warnings.append(f"Only {int(common_val.sum())} common validation points; the metrics are fragile.")

    # ---- Stumpf fits are shared by stumpf_bg/br/sw
    stumpf_fit = {}

    def get_stumpf(name):
        key = "stumpf_bg" if name == "pSDB_bg" else "stumpf_br"
        if key not in stumpf_fit:
            cal_k = ~val & np.isfinite(F_pts[name])
            if cal_k.sum() < 5:
                raise ValueError(f"{METHODS[key]}: fewer than 5 valid calibration points.")
            stumpf_fit[key] = _fit_stumpf(name, F_pts, F_img, depths, cal_k, saturation_limit,
                                          warnings, METHODS[key])
        return stumpf_fit[key]

    results, depth_rasters, trust_rasters = [], {}, {}
    for m in methods:
        own_cal = ok_by[m] & ~val
        own_val = ok_by[m] & val
        extra, sat = {}, None
        feats = feature_names(m, lyzenga_bands)
        imgs = [F_img[f] for f in feats]
        valid_img = np.all([np.isfinite(f) for f in imgs], axis=0)

        if m in ("stumpf_bg", "stumpf_br"):
            mod = get_stumpf("pSDB_bg" if m == "stumpf_bg" else "pSDB_br")
            coef, sat = mod["coef"], mod["sat"]
            pred_pts, dimg = mod["pred_pts"], mod["pred_img"].copy()
            fmin, fmax, zmin, zmax = mod["fmin"], mod["fmax"], mod["zmin"], mod["zmax"]
            fit_pts = mod["fit_pts"]
        elif m == "stumpf_sw":
            g, r = get_stumpf("pSDB_bg"), get_stumpf("pSDB_br")
            if switch_range is None:  # blend fully inside the range where red still works
                start, end = 0.5 * r["zmax"], 0.8 * r["zmax"]
            else:
                start, end = switch_range
            extra["switch"] = (float(start), float(end))
            red_pts = np.where(np.isfinite(F_pts["pSDB_br"]), r["pred_pts"], np.nan)
            red_img = np.where(np.isfinite(F_img["pSDB_br"]), r["pred_img"], np.nan)
            pred_pts, _wp = saturation.switch_blend(red_pts, g["pred_pts"], start, end)
            dimg, _wi = saturation.switch_blend(red_img, g["pred_img"], start, end)
            coef = None
            extra["coef_bg"] = [float(c) for c in g["coef"]]
            extra["coef_br"] = [float(c) for c in r["coef"]]
            sat = g["sat"]
            fmin, fmax = g["fmin"], g["fmax"]
            zmin, zmax = min(g["zmin"], r["zmin"]), g["zmax"]
            fit_pts = g["fit_pts"] | r["fit_pts"]
        elif m == "rf":
            X = np.column_stack([F_pts[f] for f in feats])
            model = _rf_model(rf_trees, seed)
            model.fit(X[own_cal], depths[own_cal])
            pred_pts = np.full(npts, np.nan)
            sd_pts = np.full(npts, np.nan)
            pred_pts[ok_by[m]], sd_pts[ok_by[m]] = rf_mean_sd(model, X[ok_by[m]])
            dimg = np.full(valid_img.shape, np.nan)
            sdimg = np.full(valid_img.shape, np.nan)
            idx = np.flatnonzero(valid_img)
            stack = np.column_stack([f.reshape(-1)[idx] for f in imgs])
            dimg.reshape(-1)[idx], sdimg.reshape(-1)[idx] = rf_mean_sd(model, stack)
            extra["sd_img"] = np.where(np.isfinite(sdimg), sdimg, NODATA).astype(np.float32)
            extra["coverage"] = coverage(depths[own_val], pred_pts[own_val], sd_pts[own_val])
            table["sd_rf"] = sd_pts
            extra["importances"] = dict(zip(feats, model.feature_importances_.tolist()))
            extra["trees"] = rf_trees
            coef = None
            fmin, fmax = X[own_cal].min(axis=0), X[own_cal].max(axis=0)
            zmin, zmax = float(depths[own_cal].min()), float(depths[own_cal].max())
            fit_pts = own_cal
        else:  # lyzenga
            X = np.column_stack([F_pts[f] for f in feats])
            coef = _fit_linear(X[own_cal], depths[own_cal])
            pred_pts = coef[0] + X @ coef[1:]
            dimg = _predict_linear(coef, imgs)
            fmin, fmax = X[own_cal].min(axis=0), X[own_cal].max(axis=0)
            zmin, zmax = float(depths[own_cal].min()), float(depths[own_cal].max())
            fit_pts = own_cal

        # trust: inside the calibrated feature ranges and depth range
        trust = np.full(dimg.shape, 255, dtype=np.uint8)
        finite = np.isfinite(dimg) & valid_img
        in_range = np.ones(int(finite.sum()), dtype=bool)
        for k, f in enumerate(imgs):
            fv = f[finite]
            in_range &= (fv >= fmin[k]) & (fv <= fmax[k])
        dv = dimg[finite]
        in_range &= (dv >= zmin) & (dv <= zmax)
        trust[finite] = in_range.astype(np.uint8)
        dimg[~finite] = NODATA
        depth_rasters[m] = dimg.astype(np.float32)
        trust_rasters[m] = trust

        pred_pts = np.where(ok_by[m], pred_pts, np.nan)
        table[f"pred_{m}"] = pred_pts
        in_lim = own_val & (depths <= zmax)
        own = validation.metrics(depths[own_val], pred_pts[own_val])
        results.append({
            "method": m, "label": METHODS[m], "split": split_txt,
            "coef": None if coef is None else [float(c) for c in coef],
            "features": feats, **extra,
            "saturation": sat, "z_lim": float(zmax), "n_fit": int(fit_pts.sum()),
            "cal": validation.metrics(depths[fit_pts], pred_pts[fit_pts]),
            "val_common": validation.metrics(depths[common_val], pred_pts[common_val]),
            "val_own": own,
            "val_own_in": validation.metrics(depths[in_lim], pred_pts[in_lim]),
            "dist_common": _distribution(depths[common_val]),
            "dist_own": _distribution(depths[own_val]),
            "bins": validation.metrics_by_bins(depths[own_val], pred_pts[own_val], bin_edges),
            "lost_alone": lost_alone[m], "n_points": npts,
            "val": own,  # kept for older callers
        })
    return results, depth_rasters, trust_rasters, table, warnings
