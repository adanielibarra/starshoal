"""Stumpf et al. (2003) log-ratio bathymetry. numpy only.

pSDB = ln(n * R_blue) / ln(n * R_other)
depth = m1 * pSDB + m0   (fitted by ordinary least squares on calibration points)
"""
import numpy as np

RATIOS = {
    "blue_green": ("blue", "green"),
    "blue_red": ("blue", "red"),
}


def log_ratio(num, den, n=1000.0):
    """Log ratio. Pixels where n*R <= 1 (log <= 0) are set to NaN.

    With n = 1000 that drops reflectances <= 0.001, which can remove a lot of
    deep-water pixels in the red band. n is exposed so it can be tuned.
    """
    num = np.asarray(num, dtype=np.float64)
    den = np.asarray(den, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        a = np.log(n * num)
        b = np.log(n * den)
        r = a / b
    bad = ~np.isfinite(r) | (a <= 0) | (b <= 0)
    r[bad] = np.nan
    return r


def fit(psdb, depth):
    """OLS fit depth = m1 * psdb + m0. Returns (m1, m0)."""
    psdb = np.asarray(psdb, dtype=np.float64)
    depth = np.asarray(depth, dtype=np.float64)
    ok = np.isfinite(psdb) & np.isfinite(depth)
    if ok.sum() < 3:
        raise ValueError("Fewer than 3 valid calibration points for the fit.")
    if np.ptp(psdb[ok]) == 0:
        raise ValueError("All calibration pSDB values are identical, cannot fit.")
    m1, m0 = np.polyfit(psdb[ok], depth[ok], 1)
    return float(m1), float(m0)


def predict(psdb, m1, m0):
    return m1 * np.asarray(psdb, dtype=np.float64) + m0
