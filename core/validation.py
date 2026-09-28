"""Calibration / validation split and accuracy metrics. numpy only."""
import numpy as np


def split_random(n, val_fraction=0.3, seed=42):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_val = int(round(n * val_fraction))
    if n_val < 1 or n_val >= n:
        raise ValueError("The split leaves calibration or validation empty.")
    val = np.zeros(n, dtype=bool)
    val[idx[:n_val]] = True
    return val


def split_blocks(x, y, block_size, val_fraction=0.3, seed=42):
    """Assign whole square blocks to validation until val_fraction of points.

    Neighbouring points look alike, so a random split inflates the scores.
    Keeping whole blocks apart gives a more honest estimate.
    Returns (val_mask, n_blocks).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    bx = np.floor(x / block_size).astype(np.int64)
    by = np.floor(y / block_size).astype(np.int64)
    keys = bx * 10_000_019 + by
    blocks, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    if len(blocks) < 2:
        raise ValueError(
            "All points fall in a single block. Use a smaller block size.")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(blocks))
    target = val_fraction * len(x)
    chosen, acc = [], 0
    for b in order:
        if acc >= target:
            break
        if acc + counts[b] >= len(x):  # never take every point
            continue
        chosen.append(b)
        acc += counts[b]
    if not chosen:
        raise ValueError("Could not build a validation set with these blocks.")
    val = np.isin(inverse, chosen)
    return val, len(blocks)


def metrics(obs, pred):
    obs = np.asarray(obs, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    ok = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[ok], pred[ok]
    n = len(obs)
    if n == 0:
        return {"n": 0, "rmse": np.nan, "mae": np.nan, "bias": np.nan, "r2": np.nan}
    err = pred - obs
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    return {
        "n": n,
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "bias": float(np.mean(err)),  # positive = predicted deeper than observed
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan,
    }


def metrics_by_bins(obs, pred, edges):
    obs = np.asarray(obs, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    rows = []
    edges = list(edges)
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (obs >= lo) & (obs < hi)
        m = metrics(obs[sel], pred[sel])
        m["range"] = f"{lo:g}-{hi:g}"
        rows.append(m)
    sel = obs >= edges[-1]
    m = metrics(obs[sel], pred[sel])
    m["range"] = f">={edges[-1]:g}"
    rows.append(m)
    return rows
