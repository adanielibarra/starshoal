"""Tests that need GDAL: zip reading, masks, file workflows and metadata."""
import numpy as np
import pytest

gdal = pytest.importorskip("osgeo.gdal")

from starshoal.core import pipeline, s2safe  # noqa: E402

from . import synth  # noqa: E402


@pytest.fixture
def scene(tmp_path):
    return synth.l2a_zip(str(tmp_path))


def test_prepare_applies_offset_and_masks(scene, tmp_path):
    zpath, depth = scene
    out = str(tmp_path / "refl.tif")
    st = s2safe.prepare(zpath, out)
    assert st["masked_cloud"] == 100 and st["masked_land"] > 0
    ds = gdal.Open(out)
    a = ds.GetRasterBand(1).ReadAsArray()
    expected = synth.reflectance(depth)["B02"][100, 150]
    assert a[100, 150] == pytest.approx(expected, abs=2e-4)   # offset -1000 applied, DN rounding
    assert a[85, 55] == s2safe.NODATA                          # cloud box


def test_prepare_polygon_mask(scene, tmp_path):
    zpath, _ = scene
    poly = "POLYGON((600500 4199500, 601500 4199500, 600500 4198500, 600500 4199500))"
    st = s2safe.prepare(zpath, str(tmp_path / "p.tif"), bounds=(600500, 4198500, 601500, 4199500), aoi_wkt=poly)
    assert st["outside_area"] > 0.4 * st["pixels"]


def test_bathymetry_file_writes_outputs_and_metadata(scene, tmp_path):
    zpath, depth = scene
    refl = str(tmp_path / "refl.tif")
    s2safe.prepare(zpath, refl)
    rng = np.random.default_rng(0)
    c, r = rng.integers(15, 190, 250), rng.integers(0, 200, 250)
    xs, ys = synth.GT[0] + (c + .5) * 10, synth.GT[3] - (r + .5) * 10
    opts = dict(methods=["stumpf_bg", "stumpf_sw"], block_size=400)
    res, warns, written = pipeline.bathymetry_file(
        refl, {"blue": 1, "green": 2, "red": 3}, xs, ys, depth[r, c], opts, out_sign=-1,
        out_dir=str(tmp_path / "out"), datum="MSL test", water_level="0.3 m (constant)", log=lambda *a: None)
    ds = gdal.Open(written["depth"][0])
    md = ds.GetMetadata()
    assert md["STARSHOAL_VERTICAL_DATUM"] == "MSL test"
    assert md["STARSHOAL_SIGN"].startswith("elevation")
    a = ds.GetRasterBand(1).ReadAsArray()
    assert np.nanmax(a[a != pipeline.NODATA]) <= 0.5          # negative elevations
    html = open(written["report"], encoding="utf-8").read()
    assert "Common RMSE" in html and "MSL test" in html


def test_rinf_mean_minus_k_sigma(tmp_path):
    bands = {"blue": np.random.default_rng(0).normal(0.02, 0.002, (100, 100))}
    wkt = "POLYGON((600000 4200000, 601000 4200000, 601000 4199000, 600000 4199000, 600000 4200000))"
    srs = gdal.osr.SpatialReference()
    srs.ImportFromEPSG(32630)
    r0 = pipeline.deep_water_rinf(bands, synth.GT, srs.ExportToWkt(), (100, 100), wkt, 0.0)["blue"]
    r2 = pipeline.deep_water_rinf(bands, synth.GT, srs.ExportToWkt(), (100, 100), wkt, 2.0)["blue"]
    assert r0 == pytest.approx(0.02, abs=2e-4) and r0 - r2 == pytest.approx(0.004, abs=3e-4)


def test_rf_uncertainty_raster(scene, tmp_path):
    pytest.importorskip("sklearn")
    zpath, depth = scene
    refl = str(tmp_path / "refl.tif")
    s2safe.prepare(zpath, refl)
    rng = np.random.default_rng(0)
    c, r = rng.integers(15, 190, 250), rng.integers(0, 200, 250)
    xs, ys = synth.GT[0] + (c + .5) * 10, synth.GT[3] - (r + .5) * 10
    res, warns, written = pipeline.bathymetry_file(
        refl, {"blue": 1, "green": 2, "red": 3}, xs, ys, depth[r, c],
        dict(methods=["stumpf_bg", "rf"], rf_trees=30, block_size=400),
        out_dir=str(tmp_path / "out"), log=lambda *a: None)
    assert len(written["sd"]) == 1
    ds = gdal.Open(written["sd"][0])
    assert "not a calibrated interval" in ds.GetMetadata()["STARSHOAL_SD"]
    assert "within 1 sd" in open(written["report"], encoding="utf-8").read()
    assert all("sd_img" not in r for r in res)


@pytest.mark.parametrize("which", ["nc", "tif"])
def test_import_acolite(tmp_path, which):
    pytest.importorskip("netCDF4")
    from starshoal.core import acolite
    nc, depth = synth.acolite_nc(str(tmp_path))
    src = nc if which == "nc" else nc.replace(".nc", "_rhos_560.tif")
    out = str(tmp_path / "out.tif")
    st = acolite.import_acolite(src, out, log=lambda m: None)
    assert st["variables"]["nir"] == ("rhos_833", 833)      # B8, not B8A (865)
    ds = gdal.Open(out)
    assert ds.GetGeoTransform() == synth.GT                 # no half-pixel shift
    a = ds.GetRasterBand(1).ReadAsArray()
    assert a[100, 100] == pytest.approx(synth.reflectance(depth)["B02"][100, 100], rel=1e-5)
    assert (a[:, :10] == s2safe.NODATA).all()               # NaN strip kept as nodata
    assert ds.GetMetadataItem("ATMOSPHERIC_CORRECTION") == "ACOLITE"


def test_import_acolite_missing_quantity(tmp_path):
    pytest.importorskip("netCDF4")
    from starshoal.core import acolite
    nc, _ = synth.acolite_nc(str(tmp_path))
    with pytest.raises(acolite.AcoliteError, match="it has rhos"):
        acolite.import_acolite(nc, str(tmp_path / "x.tif"), quantity="Rrs")
