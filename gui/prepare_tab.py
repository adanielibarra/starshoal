"""Tab 2: clip and mask a Sentinel-2 L2A zip into a 4-band reflectance GeoTIFF."""
import os

from qgis.core import QgsCoordinateReferenceSystem, QgsSettings
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                                 QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                                 QScrollArea, QVBoxLayout, QWidget)

from ..core import acolite, s2safe
from .area import AreaBox, AreaError
from .common import RunPanel, Translatable, add_raster
from .i18n import tr

S = "StarShoal/prepare/"


class PrepareTab(QWidget, Translatable):
    prepared = pyqtSignal(str)

    def __init__(self, iface, window, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        lay = QVBoxLayout(inner)

        g = QGroupBox()
        self._t(g.setTitle, "pr.input")
        f = QFormLayout(g)
        self.cb_source = QComboBox()
        self.fw_zip = QgsFileWidget()
        self.fw_zip.fileChanged.connect(self._default_out)
        self.cb_quantity = QComboBox()
        for q in acolite.QUANTITIES:
            self.cb_quantity.addItem(q, q)
        self._t(self.cb_quantity.setToolTip, "pr.quantity.tip")
        self.lbl_qty = self._lbl("pr.quantity")
        self.lbl_aco = QLabel()
        self.lbl_aco.setWordWrap(True)
        self.lbl_aco.setStyleSheet("color: gray")
        self._t(self.lbl_aco.setText, "pr.aco.help")
        f.addRow(self._lbl("pr.source"), self.cb_source)
        f.addRow(self._lbl("pr.zip"), self.fw_zip)
        f.addRow(self.lbl_qty, self.cb_quantity)
        f.addRow(self.lbl_aco)
        lay.addWidget(g)

        self.area = AreaBox(iface, window)
        lay.addWidget(self.area)

        gm = QGroupBox()
        self._t(gm.setTitle, "pr.masks")
        fm = QFormLayout(gm)
        self.chk_scl = QCheckBox()
        self._t(self.chk_scl.setText, "pr.scl")
        self._t(self.chk_scl.setToolTip, "pr.scl.tip")
        self.chk_scl.setChecked(True)
        row = QHBoxLayout()
        self.chk_ndwi = QCheckBox()
        self._t(self.chk_ndwi.setText, "pr.ndwi")
        self.chk_ndwi.setChecked(True)
        self.sp_ndwi = QDoubleSpinBox()
        self.sp_ndwi.setRange(-1, 1)
        self.sp_ndwi.setSingleStep(0.05)
        self.sp_ndwi.setValue(0.0)
        self.chk_ndwi.toggled.connect(self.sp_ndwi.setEnabled)
        row.addWidget(self.chk_ndwi)
        row.addWidget(self.sp_ndwi)
        row.addStretch()
        fm.addRow(self.chk_scl)
        fm.addRow(row)
        lay.addWidget(gm)

        go = QGroupBox()
        self._t(go.setTitle, "c.output")
        fo = QFormLayout(go)
        self.fw_out = QgsFileWidget()
        self.fw_out.setStorageMode(QgsFileWidget.StorageMode.SaveFile)
        self.fw_out.setFilter("GeoTIFF (*.tif)")
        self.chk_add = QCheckBox()
        self._t(self.chk_add.setText, "c.addmap")
        self.chk_add.setChecked(True)
        fo.addRow(self._lbl("c.outfile"), self.fw_out)
        fo.addRow("", self.chk_add)
        lay.addWidget(go)
        lay.addStretch()

        self.run = RunPanel()
        self.run.btn_run.clicked.connect(self.start)
        outer.addWidget(self.run)
        self.chk_scl.setChecked(QgsSettings().value(S + "scl", True, type=bool))
        self._retranslate_extra()
        self.cb_source.currentIndexChanged.connect(self._source_changed)
        self.cb_source.setCurrentIndex(int(QgsSettings().value(S + "source", 0)))
        self._source_changed()

    def is_acolite(self):
        return self.cb_source.currentIndex() == 1

    def _retranslate_extra(self):
        i = max(self.cb_source.currentIndex(), 0)
        self.cb_source.blockSignals(True)
        self.cb_source.clear()
        self.cb_source.addItem(tr("pr.src.l2a"))
        self.cb_source.addItem(tr("pr.src.aco"))
        self.cb_source.setCurrentIndex(i)
        self.cb_source.blockSignals(False)
        if hasattr(self, "lbl_qty"):
            self._source_changed()

    def _source_changed(self, *_):
        aco = self.is_acolite()
        self.fw_zip.setFilter("ACOLITE (*.nc *.tif *.tiff)" if aco else "Zip (*.zip)")
        self.fw_zip.setToolTip(tr("pr.aco.help" if aco else "pr.zip.tip"))
        for w in (self.lbl_qty, self.cb_quantity, self.lbl_aco):
            w.setVisible(aco)
        self.chk_scl.setEnabled(not aco)

    def set_zip(self, path):
        if path.lower().endswith(".zip"):
            self.cb_source.setCurrentIndex(0)
        self.fw_zip.setFilePath(path)

    def _default_out(self, path):
        if path and path.lower().endswith((".zip", ".nc", ".tif", ".tiff")):
            base = os.path.splitext(os.path.basename(path))[0]
            self.fw_out.setFilePath(os.path.join(os.path.dirname(path), base + "_refl.tif"))

    def start(self):
        zip_path = self.fw_zip.filePath()
        aco = self.is_acolite()
        if not zip_path or not os.path.exists(zip_path):
            self.run.error(tr("pr.need.aco" if aco else "pr.need.zip"))
            return
        out = self.fw_out.filePath()
        if not out:
            self.run.error(tr("c.need.out"))
            return
        if not out.lower().endswith(".tif"):
            out += ".tif"
        quantity = self.cb_quantity.currentData()
        try:
            wkt = acolite.crs_wkt(zip_path, quantity) if aco else s2safe.crs_wkt(zip_path)
            box, geom = self.area.get(QgsCoordinateReferenceSystem.fromWkt(wkt))
        except (AreaError, s2safe.SafeError, acolite.AcoliteError) as e:
            self.run.error(str(e))
            return
        except Exception as e:
            self.run.error(tr("c.failed", e))
            return
        bounds = None if box is None else (box.xMinimum(), box.yMinimum(), box.xMaximum(), box.yMaximum())
        if bounds is None:
            self.run.append(tr("pr.whole"), True)
        aoi = geom.asWkt() if geom is not None else None
        use_scl, use_ndwi, thr = self.chk_scl.isChecked(), self.chk_ndwi.isChecked(), self.sp_ndwi.value()
        QgsSettings().setValue(S + "scl", use_scl)
        QgsSettings().setValue(S + "source", self.cb_source.currentIndex())

        def work(log, progress, is_canceled):
            progress(5)
            if aco:
                st = acolite.import_acolite(zip_path, out, quantity=quantity, bounds=bounds, aoi_wkt=aoi,
                                            water_mask=use_ndwi, ndwi_threshold=thr, log=log)
                log(tr("pr.stats", st["pixels"], st["outside_area"], 0, st["masked_land"], st["valid_water"]))
                return out
            st = s2safe.prepare(zip_path, out, bounds=bounds, use_scl=use_scl, water_mask=use_ndwi,
                                ndwi_threshold=thr, log=lambda m: log(m, True), aoi_wkt=aoi)
            log(tr("pr.stats", st["pixels"], st["outside_area"], st["masked_cloud"],
                   st["masked_land"], st["valid_water"]))
            return out

        self.run.start("StarShoal: prepare", work, self._done)

    def _done(self, path):
        if self.chk_add.isChecked():
            add_raster(path, os.path.splitext(os.path.basename(path))[0], "rgb")
        self.prepared.emit(path)
