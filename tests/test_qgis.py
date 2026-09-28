"""Tests inside QGIS (Processing tools and the window). Skipped without QGIS."""
import os
import time

import numpy as np
import pytest

qgis_core = pytest.importorskip("qgis.core")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from . import synth  # noqa: E402


@pytest.fixture(scope="module")
def app():
    import sys
    for p in ("/usr/share/qgis/python/plugins", r"C:\OSGeo4W\apps\qgis\python\plugins"):
        if os.path.isdir(p):
            sys.path.insert(0, p)
    a = qgis_core.QgsApplication([], True)
    a.initQgis()
    from processing.core.Processing import Processing
    Processing.initialize()
    from starshoal.provider import StarShoalProvider
    prov = StarShoalProvider()
    qgis_core.QgsApplication.processingRegistry().addProvider(prov)
    yield a


def _points_layer(depth, n=250):
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
    lyr = QgsVectorLayer("Point?crs=EPSG:32630&field=de:double&field=tide:double", "pts", "memory")
    rng = np.random.default_rng(1)
    feats = []
    for _ in range(n):
        c, r = int(rng.integers(15, 190)), int(rng.integers(0, 200))
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(synth.GT[0] + (c + .5) * 10, synth.GT[3] - (r + .5) * 10)))
        f["de"] = float(depth[r, c])
        f["tide"] = 0.0
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    return lyr


def test_processing_chain(app, tmp_path):
    import processing
    zpath, depth = synth.l2a_zip(str(tmp_path))
    refl = str(tmp_path / "refl.tif")
    processing.run("starshoal:prepare_sentinel2_l2a", {"INPUT": zpath, "OUTPUT": refl})
    out = processing.run("starshoal:sdb_compare", {
        "INPUT": refl, "BLUE": 1, "GREEN": 2, "RED": 3, "POINTS": _points_layer(depth), "DEPTH_FIELD": "de",
        "TIDE_FIELD": "tide", "DATUM": "test datum", "METHODS": [0, 2], "BLOCK": 400,
        "OUT_DEPTH": str(tmp_path / "d.tif"), "OUT_TRUST": str(tmp_path / "t.tif"),
        "OUT_REPORT": str(tmp_path / "r.html"), "OUT_POINTS": str(tmp_path / "p.csv")})
    assert os.path.exists(out["OUT_DEPTH"]) and "test datum" in open(out["OUT_REPORT"], encoding="utf-8").read()


def test_window_runs_bathymetry(app, tmp_path):
    from qgis.core import QgsProject, QgsRasterLayer
    from starshoal.core import s2safe
    from starshoal.gui.main_dialog import StarShoalDialog
    zpath, depth = synth.l2a_zip(str(tmp_path))
    refl = str(tmp_path / "refl.tif")
    s2safe.prepare(zpath, refl)
    QgsProject.instance().addMapLayer(QgsRasterLayer(refl, "refl"))
    pts = _points_layer(depth)
    QgsProject.instance().addMapLayer(pts)
    dlg = StarShoalDialog(None)
    ba = dlg.bathy
    ba.set_raster(refl)
    ba.cb_pts.setLayer(pts)
    ba.cb_field.setField("de")
    ba.sp_block.setValue(400)
    ba.fw_out.setFilePath(str(tmp_path / "out"))
    ba.chk_add.setChecked(False)
    ba.start()
    t0 = time.time()
    while ba.run.task is not None and time.time() - t0 < 120:
        app.processEvents()
        time.sleep(0.05)
    assert ba.table.rowCount() >= 3, ba.run.log.toPlainText()
    dlg.home.cb_lang.setCurrentIndex(dlg.home.cb_lang.findData("en"))
    assert dlg.tabs.tabText(4) == "4 · Bathymetry"


def test_processing_import_acolite(app, tmp_path):
    pytest.importorskip("netCDF4")
    import processing
    nc, _ = synth.acolite_nc(str(tmp_path))
    out = processing.run("starshoal:import_acolite", {"INPUT": nc, "OUTPUT": str(tmp_path / "a.tif")})
    assert os.path.exists(out["OUTPUT"])


def test_window_prepares_acolite(app, tmp_path):
    pytest.importorskip("netCDF4")
    from starshoal.gui.main_dialog import StarShoalDialog
    nc, _ = synth.acolite_nc(str(tmp_path))
    dlg = StarShoalDialog(None)
    pr = dlg.prepare
    pr.cb_source.setCurrentIndex(1)
    assert pr.cb_quantity.isVisibleTo(pr) and not pr.chk_scl.isEnabled()
    pr.fw_zip.setFilePath(nc)
    pr.chk_add.setChecked(False)
    pr.start()
    t0 = time.time()
    while pr.run.task is not None and time.time() - t0 < 60:
        app.processEvents()
        time.sleep(0.05)
    assert os.path.exists(nc.replace(".nc", "_refl.tif")), pr.run.log.toPlainText()
    assert "rhos_833" in pr.run.log.toPlainText()
