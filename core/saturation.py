"""Optical depth limit of the Stumpf ratios and the red/green switching model.

detect_saturation: fits pSDB against depth with one straight line and with a
continuous two-segment line (hinge). The hinge wins only if it lowers the BIC
and the second slope is much flatter than the first (the ratio stops growing
with depth). The breakpoint is then the depth where the ratio saturates.

switch_blend: combines the blue/red model (good in very shallow water, saturates
early) with the blue/green model (reaches deeper). The switch is decided with
the blue/green depth, because the blue/red one stops growing once red saturates
and a deep pixel would look shallow. Below `start` the blue/red depth is used,
above `end` the blue/green one, and in between both are blended linearly. Where
blue/red has no value (red too dark, n*R <= 1) the blue/green depth is used.
Idea of switching ratios from Caballero and Stumpf; the switching variable and
the automatic thresholds are StarShoal's own choices.
"""
import numpy as np

MIN_POINTS = 20       # below this, no detection is attempted
EDGE_FRACTION = 0.15  # breakpoints are searched between these depth quantiles
FLAT_RATIO = 0.3      # slope after / slope before below this = flattening


def _sse_line(d, p):
    A = np.column_stack([np.ones_like(d), d])
    coef, *_ = np.linalg.lstsq(A, p, rcond=None)
    r = p - A @ coef
    return float(r @ r), coef


def _sse_hinge(d, p, c):
    A = np.column_stack([np.ones_like(d), d, np.maximum(d - c, 0.0)])
    coef, *_ = np.linalg.lstsq(A, p, rcond=None)
    r = p - A @ coef
    return float(r @ r), coef


def _bic(sse, n, k):
    return n * np.log(max(sse, 1e-12) / n) + k * np.log(n)


def detect_saturation(depth, psdb, flat_ratio=FLAT_RATIO):
    """Returns dict: saturated, z_lim, slope_before, slope_after, n, reason."""
    d = np.asarray(depth, dtype=np.float64)
    p = np.asarray(psdb, dtype=np.float64)
    ok = np.isfinite(d) & np.isfinite(p)
    d, p = d[ok], p[ok]
    n = len(d)
    out = {"saturated": False, "z_lim": float(d.max()) if n else np.nan,
           "slope_before": np.nan, "slope_after": np.nan, "n": n, "reason": ""}
    if n < MIN_POINTS:
        out["reason"] = f"only {n} calibration points (need {MIN_POINTS})"
        return out
    sse1, c1 = _sse_line(d, p)
    out["slope_before"] = out["slope_after"] = float(c1[1])
    lo, hi = np.quantile(d, [EDGE_FRACTION, 1 - EDGE_FRACTION])
    cands = np.unique(np.round(np.linspace(lo, hi, 60), 3))
    best = None
    for c in cands:
        if (d <= c).sum() < 5 or (d > c).sum() < 5:
            continue
        sse, coef = _sse_hinge(d, p, c)
        if best is None or sse < best[0]:
            best = (sse, coef, c)
    if best is None:
        out["reason"] = "not enough points on both sides of any breakpoint"
        return out
    sse2, coef, c = best
    s1, s2 = float(coef[1]), float(coef[1] + coef[2])
    better = _bic(sse2, n, 4) < _bic(sse1, n, 2)
    if better and s1 > 0 and s2 < flat_ratio * s1:
        out.update(saturated=True, z_lim=float(c), slope_before=s1, slope_after=s2,
                   reason="pSDB flattens with depth")
    else:
        out["reason"] = "no clear flattening"
    return out


def switch_blend(depth_red, depth_green, start, end):
    """Blend blue/red and blue/green depths, deciding with the blue/green one.

    Returns (depth, weight_green)."""
    dr = np.asarray(depth_red, dtype=np.float64)
    dg = np.asarray(depth_green, dtype=np.float64)
    if end <= start:
        end = start + 1e-6
    w = np.clip((dg - start) / (end - start), 0.0, 1.0)
    w = np.where(np.isfinite(dr), w, 1.0)
    out = np.where(w >= 1.0, dg, np.where(w <= 0.0, dr, (1 - w) * dr + w * dg))
    return out, w
