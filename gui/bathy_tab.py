"""Tab 4: bathymetry (Stumpf, Lyzenga, Random Forest) calibrated with depth points."""
import os

from qgis.core import (QgsFieldProxyModel, QgsMapLayerProxyModel, QgsProject,
                       QgsSettings)
from qgis.gui import QgsFieldComboBox, QgsFileWidget, QgsMapLayerComboBox
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                                 QDoubleSpinBox, QFormLayout, QGroupBox,
                                 QHBoxLayout, QHeaderView, QLineEdit,
                                 QPushButton, QScrollArea, QSpinBox,
                                 QTableWidget, QTableWidgetItem, QVBoxLayout,
                                 QWidget)

from ..algorithms.aoi import read_points, union_features
from ..algorithms.sdb_compare import settings_table
from ..author import CREDIT
from ..core import pipeline
from .common import RunPanel, Translatable, add_raster, features_of
from .i18n import tr
from .rasterbox import RasterBox

S = "StarShoal/bathy/"
METHODS = ("stumpf_bg", "stumpf_br", "stumpf_sw", "lyzenga", "rf")
COLS = ("ba.col.method", "ba.col.limit", "ba.col.nc", "ba.col.rc", "ba.col.no", "ba.col.ro",
        "ba.col.bo", "ba.col.ri", "ba.col.lost")


class BathyTab(QWidget, Translatable):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.report = None
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        body = QVBoxLayout(inner)
        cols = QHBoxLayout()
        body.addLayout(cols)
        left, right = QVBoxLayout(), QVBoxLayout()
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)

        # ---- left: image and points
        self.rbox = RasterBox(("blue", "green", "red"))
        left.addWidget(self.rbox)

        gp = QGroupBox()
        self._t(gp.setTitle, "ba.points")
        fp = QFormLayout(gp)
        fp.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        fp.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.cb_pts = QgsMapLayerComboBox()
        self.cb_pts.setFilters(QgsMapLayerProxyModel.Filter.PointLayer)
        self.cb_field = QgsFieldComboBox()
        self.cb_field.setFilters(QgsFieldProxyModel.Filter.Numeric)
        self.cb_pts.layerChanged.connect(self.cb_field.setLayer)
        self.cb_field.setLayer(self.cb_pts.currentLayer())
        self.chk_sel = QCheckBox()
        self._t(self.chk_sel.setText, "c.selected")
        self.cb_sign = QComboBox()
        self.sp_tide = QDoubleSpinBox()
        self.sp_tide.setRange(-20, 20)
        self.sp_tide.setDecimals(3)
        self.sp_tide.setSuffix(" m")
        self._t(self.sp_tide.setToolTip, "ba.tide.tip")
        fp.addRow(self._lbl("ba.pts"), self.cb_pts)
        fp.addRow("", self.chk_sel)
        fp.addRow(self._lbl("ba.field"), self.cb_field)
        fp.addRow(self._lbl("ba.sign"), self.cb_sign)
        fp.addRow(self._lbl("ba.tide"), self.sp_tide)
        self.cb_tidefield = QgsFieldComboBox()
        self.cb_tidefield.setFilters(QgsFieldProxyModel.Filter.Numeric)
        self.cb_tidefield.setAllowEmptyFieldName(True)
        self.cb_pts.layerChanged.connect(self.cb_tidefield.setLayer)
        self.cb_tidefield.setLayer(self.cb_pts.currentLayer())
        self.cb_tidefield.setField("")
        self._t(self.cb_tidefield.setToolTip, "ba.tidefield.tip")
        self.le_datum = QLineEdit()
        self._t(self.le_datum.setPlaceholderText, "ba.datum.ph")
        self._t(self.le_datum.setToolTip, "ba.datum.tip")
        fp.addRow(self._lbl("ba.tidefield"), self.cb_tidefield)
        fp.addRow(self._lbl("ba.datum"), self.le_datum)
        left.addWidget(gp)

        go = QGroupBox()
        self._t(go.setTitle, "c.output")
        fo = QFormLayout(go)
        fo.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        fo.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.fw_out = QgsFileWidget()
        self.fw_out.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)
        self.cb_outsign = QComboBox()
        self.chk_add = QCheckBox()
        self._t(self.chk_add.setText, "c.addmap")
        self.chk_add.setChecked(True)
        self.chk_trust = QCheckBox()
        self._t(self.chk_trust.setText, "ba.addtrust")
        fo.addRow(self._lbl("c.outdir"), self.fw_out)
        fo.addRow(self._lbl("ba.outsign"), self.cb_outsign)
        fo.addRow("", self.chk_add)
        fo.addRow("", self.chk_trust)
        left.addWidget(go)
        left.addStretch()

        # ---- right: methods and validation
        gm = QGroupBox()
        self._t(gm.setTitle, "ba.methods")
        fm = QFormLayout(gm)
        fm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        fm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.chk_m = {}
        for m in METHODS:
            c = QCheckBox()
            self._t(c.setText, "ba.m." + m)
            c.setChecked(m != "rf")
            self.chk_m[m] = c
            fm.addRow(c)
        self.chk_sat = QCheckBox()
        self._t(self.chk_sat.setText, "ba.sat")
        self._t(self.chk_sat.setToolTip, "ba.sat.tip")
        self.chk_sat.setChecked(True)
        fm.addRow(self.chk_sat)
        swrow = QHBoxLayout()
        self.sp_sw = []
        for _ in range(2):
            sp = QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setSuffix(" m")
            self._t(sp.setSpecialValueText, "ba.auto")
            self._t(sp.setToolTip, "ba.sw.tip")
            self.sp_sw.append(sp)
            swrow.addWidget(sp)
        fm.addRow(self._lbl("ba.sw"), swrow)
        lrow = QHBoxLayout()
        self.chk_lb = {}
        for b in ("blue", "green", "red"):
            c = QCheckBox()
            self._t(c.setText, "ba.b." + b)
            c.setChecked(b != "red")
            self.chk_lb[b] = c
            lrow.addWidget(c)
        lrow.addStretch()
        fm.addRow(self._lbl("ba.lyz.bands"), lrow)
        self.cb_deep = QgsMapLayerComboBox()
        self.cb_deep.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        self.cb_deep.setAllowEmptyLayer(True)
        self.cb_deep.setLayer(None)
        self._t(self.cb_deep.setToolTip, "ba.deep.tip")
        fm.addRow(self._lbl("ba.deep"), self.cb_deep)
        self.sp_k = QDoubleSpinBox()
        self.sp_k.setRange(0, 5)
        self.sp_k.setSingleStep(0.5)
        self.sp_k.setValue(2.0)
        fm.addRow(self._lbl("ba.k"), self.sp_k)
        self.sp_trees = QSpinBox()
        self.sp_trees.setRange(10, 5000)
        self.sp_trees.setValue(300)
        self.sp_n = QDoubleSpinBox()
        self.sp_n.setRange(1, 1e6)
        self.sp_n.setDecimals(0)
        self.sp_n.setValue(1000)
        fm.addRow(self._lbl("ba.trees"), self.sp_trees)
        fm.addRow(self._lbl("ba.n"), self.sp_n)
        right.addWidget(gm)

        gv = QGroupBox()
        self._t(gv.setTitle, "ba.val")
        fv = QFormLayout(gv)
        fv.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        fv.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.cb_split = QComboBox()
        self.sp_block = QDoubleSpinBox()
        self.sp_block.setRange(1, 1e6)
        self.sp_block.setDecimals(0)
        self.sp_block.setValue(500)
        self.sp_block.setSuffix(" m")
        self.cb_split.currentIndexChanged.connect(lambda i: self.sp_block.setEnabled(i == 0))
        self.sp_block.setMinimumWidth(90)
        self.sp_val = QDoubleSpinBox()
        self.sp_val.setRange(0.05, 0.9)
        self.sp_val.setSingleStep(0.05)
        self.sp_val.setValue(0.3)
        self.sp_seed = QSpinBox()
        self.sp_seed.setRange(0, 2 ** 31 - 1)
        self.sp_seed.setValue(42)
        self.cb_window = QComboBox()
        self.chk_agg = QCheckBox()
        self._t(self.chk_agg.setText, "ba.aggregate")
        self.chk_agg.setChecked(True)
        self.le_bins = QLineEdit("0,2,5,10,15,20")
        fv.addRow(self._lbl("ba.split"), self.cb_split)
        fv.addRow(self._lbl("ba.block"), self.sp_block)
        fv.addRow(self._lbl("ba.valfrac"), self.sp_val)
        fv.addRow(self._lbl("ba.seed"), self.sp_seed)
        fv.addRow(self._lbl("ba.window"), self.cb_window)
        fv.addRow("", self.chk_agg)
        fv.addRow(self._lbl("ba.bins"), self.le_bins)
        right.addWidget(gv)

        gr = QGroupBox()
        self._t(gr.setTitle, "ba.results")
        vr = QVBoxLayout(gr)
        self.table = QTableWidget(0, len(COLS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(150)
        vr.addWidget(self.table)
        self.btn_report = QPushButton()
        self._t(self.btn_report.setText, "ba.open")
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self._open_report)
        vr.addWidget(self.btn_report)
        right.addStretch()
        body.addWidget(gr)

        self.run = RunPanel()
        self.run.btn_run.clicked.connect(self.start)
        outer.addWidget(self.run)
        self._retranslate_extra()
        self.fw_out.setFilePath(QgsSettings().value(S + "out", ""))

    # ------------------------------------------------------------ helpers
    def set_raster(self, path):
        self.rbox.set_path(path)

    def _refill(self, combo, keys):
        i = max(combo.currentIndex(), 0)
        combo.clear()
        for k in keys:
            combo.addItem(tr(k))
        combo.setCurrentIndex(i)

    def _retranslate_extra(self):
        self._refill(self.cb_sign, ("ba.sign.depth", "ba.sign.elev"))
        self._refill(self.cb_outsign, ("ba.sign.depth", "ba.sign.elev"))
        self._refill(self.cb_split, ("ba.split.blocks", "ba.split.random"))
        self._refill(self.cb_window, ("ba.window.1", "ba.window.3"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in COLS])

    def _open_report(self):
        if self.report and os.path.exists(self.report):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.report))

    # ------------------------------------------------------------ run
    def start(self):
        lyr = self.rbox.layer()
        if lyr is None:
            self.run.error(tr("c.need.raster"))
            return
        pts, field = self.cb_pts.currentLayer(), self.cb_field.currentField()
        if pts is None or not field:
            self.run.error(tr("ba.need.pts"))
            return
        methods = [m for m in METHODS if self.chk_m[m].isChecked()]
        if not methods:
            self.run.error(tr("ba.need.method"))
            return
        lyz = [b for b in ("blue", "green", "red") if self.chk_lb[b].isChecked()]
        if "lyzenga" in methods and not lyz:
            self.run.error(tr("ba.need.lyz"))
            return
        out_dir = self.fw_out.filePath()
        if not out_dir:
            self.run.error(tr("c.need.out"))
            return
        try:
            edges = [float(s) for s in self.le_bins.text().split(",") if s.strip()]
        except ValueError:
            self.run.error(tr("c.failed", self.le_bins.text()))
            return
        QgsSettings().setValue(S + "out", out_dir)

        tctx = QgsProject.instance().transformContext()
        sign = -1.0 if self.cb_sign.currentIndex() == 1 else 1.0
        tide = self.sp_tide.value()
        tide_field = self.cb_tidefield.currentField() or None
        xs, ys, depths, skipped, fallback = read_points(features_of(pts, self.chk_sel.isChecked()), pts.crs(),
                                                        lyr.crs(), tctx, field, sign, tide, tide_field)
        if fallback:
            self.run.append(tr("ba.fallback", fallback), True)
        if skipped:
            self.run.append(tr("ba.skipped", skipped), True)
        if len(xs) < 10:
            self.run.error(tr("ba.few", len(xs)))
            return
        deep_wkt = None
        deep = self.cb_deep.currentLayer()
        if deep is not None and "lyzenga" in methods:
            g, _n = union_features(deep.getFeatures(), deep.crs(), lyr.crs(), tctx)
            if g is None:
                self.run.error(tr("c.nopoly"))
                return
            deep_wkt = g.asWkt()

        opts = dict(methods=methods, lyzenga_bands=lyz, rf_trees=self.sp_trees.value(),
                    n_const=self.sp_n.value(), window=3 if self.cb_window.currentIndex() == 1 else 1,
                    aggregate=self.chk_agg.isChecked(),
                    split="blocks" if self.cb_split.currentIndex() == 0 else "random",
                    block_size=self.sp_block.value(), val_fraction=self.sp_val.value(),
                    seed=self.sp_seed.value(), bin_edges=edges,
                    saturation_limit=self.chk_sat.isChecked(), switch_range=None)
        a, b = self.sp_sw[0].value(), self.sp_sw[1].value()
        if a > 0 and b > 0:
            if b <= a:
                self.run.error(tr("ba.sw.tip"))
                return
            opts["switch_range"] = (a, b)
        out_sign = -1.0 if self.cb_outsign.currentIndex() == 1 else 1.0
        settings = settings_table(lyr.source(), pts.name(), field, sign, tide, opts)
        water = (f"field '{tide_field}' (constant {tide} m where empty)" if tide_field
                 else f"{tide} m (constant)")
        datum, k_sigma = self.le_datum.text().strip(), self.sp_k.value()
        src, idx = lyr.source(), self.rbox.indices()
        self.btn_report.setEnabled(False)
        self.table.setRowCount(0)

        def work(log, progress, is_canceled):
            progress(10)
            return pipeline.bathymetry_file(src, idx, xs, ys, depths, opts, deep_wkt=deep_wkt,
                                            out_sign=out_sign, out_dir=out_dir, settings=settings,
                                            credit=CREDIT, log=log, k_sigma=k_sigma,
                                            datum=datum, water_level=water)

        self._out_sign = out_sign
        self.run.start("StarShoal: bathymetry", work, self._done)

    def _done(self, result):
        results, _warns, written = result
        self.table.setRowCount(len(results))
        def f2(x, fmt="{:.2f}"):
            return "n/a" if x != x else fmt.format(x)

        for r, res in enumerate(results):
            c, o, i = res["val_common"], res["val_own"], res["val_own_in"]
            vals = [tr("ba.m." + res["method"]).split(" (")[0], f2(res["z_lim"], "{:.1f}"),
                    str(c["n"]), f2(c["rmse"]), str(o["n"]), f2(o["rmse"]), f2(o["bias"], "{:+.2f}"),
                    f2(i["rmse"]), f"{res['lost_alone']} / {res['n_points']}"]
            for c, val in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.report = written.get("report")
        self.btn_report.setEnabled(bool(self.report))
        if self.chk_add.isChecked():
            if self.chk_trust.isChecked():
                for p in written["trust"]:
                    add_raster(p, os.path.splitext(os.path.basename(p))[0])
            for p in written.get("sd", []):
                add_raster(p, os.path.splitext(os.path.basename(p))[0], "sd")
            for p in written["depth"]:
                add_raster(p, os.path.splitext(os.path.basename(p))[0], "depth",
                           inverted=self._out_sign < 0)
