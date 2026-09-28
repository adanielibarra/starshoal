"""numpy-only tests of the methods (no GDAL, no QGIS)."""
import numpy as np
import pytest

from starshoal.core import deglint, saturation, sdb, stumpf, validation

from . import synth


def test_log_ratio_masks_dark_pixels():
    r = stumpf.log_ratio(np.array([0.05, 0.0005]), np.array([0.04, 0.04]), 1000)
    assert np.isfinite(r[0]) and np.isnan(r[1])


def test_blocks_keep_whole_blocks_apart():
    rng = np.random.default_rng(0)
    x, y = rng.uniform(0, 1000, 300), rng.uniform(0, 1000, 300)
    val, nb = validation.split_blocks(x, y, 250, 0.3, 1)
    assert nb > 4 and 0.2 < val.mean() < 0.5
    key = (np.floor(x / 250) * 1000 + np.floor(y / 250))
    for k in np.unique(key):   # a block is entirely cal or entirely val
        assert len(set(val[key == k])) == 1


def test_metrics_basic():
    m = validation.metrics([1, 2, 3], [2, 3, 4])
    assert m["bias"] == pytest.approx(1) and m["rmse"] == pytest.approx(1)


def test_hedley_removes_flat_glint():
    rng = np.random.default_rng(3)
    base = np.full((100, 100), 0.02)
    glint = np.abs(rng.normal(0, 0.02, base.shape))
    vis, nir = [base + glint], 0.001 + glint
    p = deglint.fit(vis, nir, np.ones(base.shape, bool))
    out = deglint.apply(vis, nir, p)[0]
    assert p["bands"][0]["r2"] > 0.99
    assert np.abs(out - base).mean() < 1e-3


def test_red_ratio_saturates_green_goes_deeper():
    depth, bands = synth.ramp(zmax=30)
    xs, ys, d = synth.points(depth, 600, max_col=230)
    rows, cols = sdb.pixel_index(synth.GT, xs, ys)
    for num, den, lo, hi in (("blue", "red", 3, 11), ("blue", "green", 10, 22)):
        p = sdb.sample(stumpf.log_ratio(bands[num], bands[den]), rows, cols)
        s = saturation.detect_saturation(d, p)
        assert s["saturated"] and lo < s["z_lim"] < hi, (num, den, s)


def test_no_saturation_on_a_straight_line():
    d = np.linspace(0, 10, 200)
    s = saturation.detect_saturation(d, 1 + 0.1 * d + np.random.default_rng(0).normal(0, 0.01, 200))
    assert not s["saturated"]


def test_switch_blend_uses_green_depth_to_decide():
    red = np.array([1.0, 6.0, 6.0, np.nan])     # red saturates at ~6 m
    green = np.array([1.2, 4.0, 20.0, 15.0])
    out, w = saturation.switch_blend(red, green, 3.0, 5.0)
    assert out[0] == pytest.approx(1.0)          # shallow: red
    assert out[2] == pytest.approx(20.0)         # deep: green, even if red says 6
    assert out[3] == pytest.approx(15.0)         # no red: green
    assert 0 < w[1] < 1                          # blend zone


def test_saturation_limit_improves_the_shallow_part():
    depth, bands = synth.ramp(zmax=30)
    xs, ys, d = synth.points(depth, 500, max_col=230)
    off = sdb.run(bands, synth.GT, xs, ys, d, methods=("stumpf_br",), block_size=400, saturation_limit=False)[0][0]
    on = sdb.run(bands, synth.GT, xs, ys, d, methods=("stumpf_br",), block_size=400, saturation_limit=True)[0][0]
    assert on["saturation"]["saturated"]
    assert on["val_own_in"]["rmse"] < 1.0 < off["val_own_in"]["rmse"]


def test_common_sample_is_shallower_when_a_method_loses_deep_points():
    depth, bands = synth.ramp(zmax=30)
    xs, ys, d = synth.points(depth, 500, max_col=230)
    r_inf = {"blue": 0.012, "green": 0.008, "red": 0.002}
    res, *_ = sdb.run(bands, synth.GT, xs, ys, d, methods=("stumpf_bg", "lyzenga"), r_inf=r_inf,
                      lyzenga_bands=("blue", "green", "red"), block_size=400)
    bg, lz = res
    assert lz["lost_alone"] > 50 and bg["lost_alone"] == 0
    assert bg["val_common"]["n"] < bg["val_own"]["n"]
    assert bg["dist_common"]["median"] < bg["dist_own"]["median"]


def test_all_methods_share_one_split():
    depth, bands = synth.ramp(zmax=20)
    xs, ys, d = synth.points(depth, 300)
    res, dr, tr, table, warns = sdb.run(bands, synth.GT, xs, ys, d,
                                        methods=("stumpf_bg", "stumpf_br", "stumpf_sw", "lyzenga"), block_size=500)
    assert set(table["set"]) == {"cal", "val"}
    assert len({r["split"] for r in res}) == 1
    for m in ("stumpf_bg", "stumpf_sw"):
        assert (tr[m] == 1).any() and dr[m].dtype == np.float32


def test_random_forest_if_available():
    pytest.importorskip("sklearn")
    depth, bands = synth.ramp(zmax=20)
    xs, ys, d = synth.points(depth, 300)
    res, *_ = sdb.run(bands, synth.GT, xs, ys, d, methods=("rf",), rf_trees=30, block_size=500)
    assert res[0]["val_own"]["rmse"] < 2.0


def test_rf_spread_and_coverage():
    pytest.importorskip("sklearn")
    depth, bands = synth.ramp(zmax=20)
    xs, ys, d = synth.points(depth, 300)
    res, _dr, _tr, table, _w = sdb.run(bands, synth.GT, xs, ys, d, methods=("rf",), rf_trees=40, block_size=500)
    r = res[0]
    sd = r["sd_img"]
    assert sd.dtype == np.float32 and (sd[sd != sdb.NODATA] >= 0).all()
    cv = r["coverage"]
    assert cv["n"] > 0 and 0 <= cv["within1"] <= cv["within2"] <= 1
    assert "sd_rf" in table


def test_rf_mean_equals_forest_prediction():
    pytest.importorskip("sklearn")
    from sklearn.ensemble import RandomForestRegressor
    rng = np.random.default_rng(0)
    X, y = rng.normal(size=(200, 3)), rng.normal(size=200)
    m = RandomForestRegressor(n_estimators=20, random_state=0).fit(X, y)
    mean, sd = sdb.rf_mean_sd(m, X, chunk=37)
    assert np.allclose(mean, m.predict(X)) and (sd >= 0).all()


def test_cdse_refuses_non_https():
    from starshoal.core import cdse
    with pytest.raises(cdse.CDSEError, match="non-https"):
        cdse._urlopen("file:///etc/passwd", 5)
