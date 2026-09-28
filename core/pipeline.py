"""File-level workflows shared by the StarShoal window and the Processing tools.

No QGIS imports: points arrive as coordinates already in the raster CRS and
polygons as WKT in the raster CRS. log(msg, warn=False) reports progress.
"""
import csv
import os

import numpy as np
from osgeo import gdal

from . import deglint, report, sdb
from .s2safe import polygon_mask

gdal.UseExceptions()
NODATA = -9999.0


def _log(msg, warn=False):
    print(("WARNING: " if warn else "") + msg)


def read_bands(path, idx):
    """idx: {name: band number}. Returns (arrays, geotransform, projection, (w, h))."""
    ds = gdal.Open(path)
    gt = ds.GetGeoTransform()
    if gt[2] != 0 or gt[4] != 0:
        raise ValueError("Rotated rasters are not supported.")
    out = {}
    for name, i in idx.items():
        if i < 1 or i > ds.RasterCount:
            raise ValueError(f"Band {i} does not exist (the raster has {ds.RasterCount}).")
        b = ds.GetRasterBand(i)
        a = b.ReadAsArray().astype(np.float64)
        nd = b.GetNoDataValue()
        if nd is not None:
            a[a == nd] = np.nan
        out[name] = a
    return out, gt, ds.GetProjection(), (ds.RasterXSize, ds.RasterYSize)


def write_raster(path, arrays, names, gt, proj, dtype=gdal.GDT_Float32, nodata=NODATA, metadata=None):
    h, w = arrays[0].shape
    o = gdal.GetDriverByName("GTiff").Create(path, w, h, len(arrays), dtype,
                                             options=["COMPRESS=DEFLATE", "TILED=YES"])
    o.SetGeoTransform(gt)
    o.SetProjection(proj)
    for k, v in (metadata or {}).items():
        o.SetMetadataItem(str(k), str(v))
    for i, (a, n) in enumerate(zip(arrays, names), start=1):
        b = o.GetRasterBand(i)
        b.WriteArray(a)
        b.SetNoDataValue(nodata)
        b.SetDescription(n)
    o.FlushCache()
    o = None
    return path


def deglint_file(in_path, idx, deep_wkt, out_path, percentile=0.0, log=_log):
    """Hedley sunglint correction. idx needs blue, green, red, nir. Returns the fit."""
    b, gt, proj, (w, h) = read_bands(in_path, idx)
    sample = polygon_mask(deep_wkt, gt, w, h, proj)
    p = deglint.fit([b["blue"], b["green"], b["red"]], b["nir"], sample, percentile)
    log(f"Deep-water sample: {p['n']} pixels, NIR reference {p['nir_ref']:.5f}")
    for name, bb in zip(("blue", "green", "red"), p["bands"]):
        log(f"  {name}: slope {bb['slope']:.3f}, R² {bb['r2']:.3f}")
        if bb["r2"] < 0.3:
            log(f"  {name}: low R², the glint model is weak for this band.", True)
    vis = deglint.apply([b["blue"], b["green"], b["red"]], b["nir"], p)
    n_neg = sum(int((np.isfinite(v) & (v <= 0)).sum()) for v in vis)
    if n_neg:
        log(f"{n_neg} band values became <= 0 after correction; they will be invalid "
            "for the log-based methods.", True)
    arrays = [np.where(np.isfinite(a), a, NODATA).astype(np.float32) for a in vis + [b["nir"]]]
    write_raster(out_path, arrays, ["B02", "B03", "B04", "B08"], gt, proj)
    return p


def deep_water_rinf(bands, gt, proj, size, deep_wkt, k_sigma=2.0, log=_log):
    """R_inf per band = mean - k_sigma * standard deviation inside the deep-water polygon.

    With k_sigma = 0 it is the plain mean; subtracting k standard deviations keeps
    fewer pixels below R_inf (which would be lost for Lyzenga).
    """
    w, h = size
    deep = polygon_mask(deep_wkt, gt, w, h, proj)
    r_inf = {}
    for k, a in bands.items():
        v = a[deep & np.isfinite(a)]
        if len(v) < 50:
            raise ValueError(f"Only {len(v)} valid pixels in the deep-water polygon; need at least 50.")
        r_inf[k] = float(v.mean() - k_sigma * v.std())
        if r_inf[k] <= 0:
            log(f"R_inf of {k} is {r_inf[k]:.5f} (<= 0) with k = {k_sigma:g}; ln(R - R_inf) still works, "
                "but the deep-water sample is very noisy or very dark.", True)
    return r_inf


def bathymetry_file(in_path, idx, xs, ys, depths, options, deep_wkt=None, out_sign=1.0,
                    out_depth=None, out_trust=None, out_dir=None, out_report=None,
                    out_points=None, settings=(), credit="", log=_log, k_sigma=2.0,
                    datum="", water_level="", out_sd=None):
    """Run sdb.run on a raster file and write every output.

    Either out_depth/out_trust (one multiband file each, band per method) or
    out_dir (one file per method: depth_<method>.tif, trust_<method>.tif).
    Returns (results, warnings, written) where written maps kind -> paths.
    """
    bands, gt, proj, size = read_bands(in_path, idx)
    r_inf = None
    if deep_wkt and "lyzenga" in options.get("methods", ()):
        r_inf = deep_water_rinf(bands, gt, proj, size, deep_wkt, k_sigma, log)
        log(f"Lyzenga R_inf (deep-water mean - {k_sigma:g} sd): " +
            ", ".join(f"{k} {v:.5f}" for k, v in r_inf.items()))

    results, depth_r, trust_r, table, warns = sdb.run(bands, gt, xs, ys, depths, r_inf=r_inf, **options)
    for w in warns:
        log(w, True)
    if not results:
        raise ValueError("No method could be fitted. See the warnings.")

    names = [r["method"] for r in results]
    if out_sign < 0:
        for n in names:
            a = depth_r[n]
            a[a != NODATA] *= -1.0

    meta = {"STARSHOAL_UNITS": "m",
            "STARSHOAL_SIGN": "elevation, negative down" if out_sign < 0 else "depth, positive down",
            "STARSHOAL_VERTICAL_DATUM": datum or "not given",
            "STARSHOAL_WATER_LEVEL": water_level or "not given",
            "STARSHOAL_SOURCE": os.path.basename(in_path)}
    zlim = {r["method"]: r["z_lim"] for r in results}
    written = {"depth": [], "trust": [], "sd": []}
    sd_rf = None
    for r in results:
        if "sd_img" in r:
            sd_rf = r.pop("sd_img")
    sd_md = dict(meta, STARSHOAL_METHOD="rf",
                 STARSHOAL_SD="standard deviation of the tree predictions (m); relative, not a calibrated interval")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        for n in names:
            md = dict(meta, STARSHOAL_METHOD=n, STARSHOAL_DEPTH_LIMIT_M=f"{zlim[n]:.2f}")
            written["depth"].append(write_raster(os.path.join(out_dir, f"depth_{n}.tif"),
                                                 [depth_r[n]], [n], gt, proj, metadata=md))
            written["trust"].append(write_raster(os.path.join(out_dir, f"trust_{n}.tif"),
                                                 [trust_r[n]], [n], gt, proj, gdal.GDT_Byte, 255,
                                                 metadata=dict(md, STARSHOAL_TRUST="1 calibrated, 0 extrapolated, 255 no data")))
        if sd_rf is not None:
            written["sd"].append(write_raster(os.path.join(out_dir, "sd_rf.tif"), [sd_rf], ["sd_rf"],
                                              gt, proj, metadata=sd_md))
        out_report = out_report or os.path.join(out_dir, "report.html")
        out_points = out_points or os.path.join(out_dir, "points.csv")
    else:
        if out_depth:
            written["depth"].append(write_raster(out_depth, [depth_r[n] for n in names], names, gt, proj,
                                                 metadata=dict(meta, STARSHOAL_METHODS=",".join(names))))
        if out_trust:
            written["trust"].append(write_raster(out_trust, [trust_r[n] for n in names], names,
                                                 gt, proj, gdal.GDT_Byte, 255,
                                                 metadata=dict(meta, STARSHOAL_METHODS=",".join(names))))

    if not out_dir and out_sd and sd_rf is not None:
        written["sd"].append(write_raster(out_sd, [sd_rf], ["sd_rf"], gt, proj, metadata=sd_md))
    for r in results:
        c, o = r["val_common"], r["val_own"]
        log(f"{r['label']}: depth limit {r['z_lim']:.1f} m | common n={c['n']} RMSE={c['rmse']:.2f} m | "
            f"own n={o['n']} RMSE={o['rmse']:.2f} m bias={o['bias']:+.2f} m")
        if "coverage" in r:
            cv = r["coverage"]
            log(f"  Random Forest spread between trees: mean {cv['mean_sd']:.2f} m; validation errors within "
                f"1 sd {100 * cv['within1']:.0f} % and within 2 sd {100 * cv['within2']:.0f} % "
                "(68 % and 95 % if it were a calibrated normal interval).")

    settings = list(settings) + [
        ("Vertical datum", datum or "not given"),
        ("Water level added", water_level or "not given"),
        ("Lyzenga R_inf", f"deep-water mean - {k_sigma:g} sd" if r_inf else "0 (no deep-water polygon)"),
        ("Output sign", "elevation, negative down" if out_sign < 0 else "depth, positive down"),
    ]
    if out_report:
        with open(out_report, "w", encoding="utf-8") as fh:
            fh.write(report.build(settings, results, warns, credit))
        written["report"] = out_report
    if out_points:
        tab = table
        if out_sign < 0:
            tab = {("elevation" if k == "depth" else k):
                   (-v if (k == "depth" or k.startswith("pred_")) else v) for k, v in table.items()}
        cols = list(tab.keys())
        with open(out_points, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(cols)
            for i in range(len(tab["x"])):
                row = []
                for c in cols:
                    v = tab[c][i]
                    row.append("" if isinstance(v, float) and np.isnan(v) else v)
                wr.writerow(row)
        written["points"] = out_points
    return results, warns, written
