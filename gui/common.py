"""Pieces shared by the StarShoal tabs."""
import traceback

from qgis.core import (Qgis, QgsApplication, QgsColorRampShader,
                       QgsContrastEnhancement, QgsMessageLog,
                       QgsMultiBandColorRenderer, QgsProject, QgsRasterLayer,
                       QgsRasterShader, QgsSingleBandPseudoColorRenderer,
                       QgsStyle, QgsTask)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit,
                                 QProgressBar, QPushButton, QVBoxLayout,
                                 QWidget)

from .i18n import tr

TAG = "StarShoal"
GROUP = "StarShoal"


class Translatable:
    """Remembers which widget texts come from which key, to switch language live."""

    def _t(self, setter, key, *args):
        if not hasattr(self, "_tr_items"):
            self._tr_items = []
        setter(tr(key, *args))
        self._tr_items.append((setter, key, args))

    def _lbl(self, key):
        lab = QLabel()
        self._t(lab.setText, key)
        return lab

    def retranslate(self):
        for setter, key, args in getattr(self, "_tr_items", []):
            setter(tr(key, *args))
        self._retranslate_extra()

    def _retranslate_extra(self):
        """Override for things that are not a single setter (combo items, headers...)."""


class FunctionTask(QgsTask):
    """Runs fn(log=, progress=, is_canceled=) in the background; result in .result."""
    message = pyqtSignal(str, bool)

    def __init__(self, title, fn):
        super().__init__(title, QgsTask.Flag.CanCancel)
        self.fn = fn
        self.result = None
        self.error = None

    def _log(self, msg, warn=False):
        self.message.emit(str(msg), bool(warn))

    def run(self):
        try:
            self.result = self.fn(log=self._log, progress=self.setProgress,
                                  is_canceled=self.isCanceled)
            return not self.isCanceled()
        except Exception as e:  # reported in the panel and the QGIS log
            self.error = str(e) or e.__class__.__name__
            QgsMessageLog.logMessage(traceback.format_exc(), TAG, Qgis.MessageLevel.Warning)
            return False


class RunPanel(QWidget, Translatable):
    """Run and Cancel buttons, a progress bar and a log box."""

    def __init__(self, run_key="c.run", parent=None):
        super().__init__(parent)
        self.task = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.btn_run = QPushButton()
        self._t(self.btn_run.setText, run_key)
        self.btn_cancel = QPushButton()
        self._t(self.btn_cancel.setText, "c.cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        row.addWidget(self.bar, 1)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_run)
        lay.addLayout(row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setMinimumHeight(90)
        self.log.setMaximumHeight(150)
        lay.addWidget(self.log)

    def busy(self):
        return self.task is not None

    def append(self, msg, warn=False):
        if warn:
            self.log.appendHtml(f"<span style='color:#b35c00'>{_esc(msg)}</span>")
        else:
            self.log.appendPlainText(msg)

    def error(self, msg):
        self.log.appendHtml(f"<span style='color:#c0392b'><b>{_esc(msg)}</b></span>")

    def start(self, title, fn, on_done=None, extra_buttons=()):
        """Launch fn in a QgsTask. on_done(result) runs in the main thread if it succeeds."""
        if self.task is not None:
            self.error(tr("c.busy"))
            return
        self.bar.setValue(0)
        self._extra = list(extra_buttons)
        for b in [self.btn_run] + self._extra:
            b.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        task = FunctionTask(title, fn)
        task.message.connect(self.append)
        task.progressChanged.connect(lambda p: self.bar.setValue(int(p)))
        task.taskCompleted.connect(lambda: self._finish(True, on_done))
        task.taskTerminated.connect(lambda: self._finish(False, on_done))
        self.task = task
        QgsApplication.taskManager().addTask(task)

    def _finish(self, ok, on_done):
        task, self.task = self.task, None
        for b in [self.btn_run] + getattr(self, "_extra", []):
            b.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if task is None:
            return
        if ok:
            self.bar.setValue(100)
            try:
                if on_done:
                    on_done(task.result)
                self.append(tr("c.done"))
            except Exception as e:
                self.error(tr("c.failed", e))
                QgsMessageLog.logMessage(traceback.format_exc(), TAG, Qgis.MessageLevel.Warning)
        elif task.error:
            self.error(tr("c.failed", task.error))
        else:
            self.append(tr("c.canceled"), True)

    def cancel(self):
        if self.task is not None:
            self.task.cancel()


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def add_raster(path, name, style=None, inverted=False):
    """Add a raster to the StarShoal group. style: 'rgb' (bands 3,2,1) or 'depth'."""
    lyr = QgsRasterLayer(path, name)
    if not lyr.isValid():
        return None
    try:
        if style == "rgb" and lyr.bandCount() >= 3:
            r = QgsMultiBandColorRenderer(lyr.dataProvider(), 3, 2, 1)
            lyr.setRenderer(r)
            lyr.setContrastEnhancement(QgsContrastEnhancement.ContrastEnhancementAlgorithm.StretchToMinimumMaximum)
        elif style in ("depth", "sd"):
            st = lyr.dataProvider().bandStatistics(1)
            ramp = QgsStyle.defaultStyle().colorRamp("Blues" if style == "depth" else "Reds")
            if ramp is not None:
                if inverted:
                    ramp.invert()
                fn = QgsColorRampShader(st.minimumValue, st.maximumValue, ramp)
                fn.classifyColorRamp(5, -1)
                shader = QgsRasterShader()
                shader.setRasterShaderFunction(fn)
                lyr.setRenderer(QgsSingleBandPseudoColorRenderer(lyr.dataProvider(), 1, shader))
    except Exception as e:  # styling is a nicety, never a reason to fail
        QgsMessageLog.logMessage(f"Style for {name}: {e}", TAG, Qgis.MessageLevel.Info)
    root = QgsProject.instance().layerTreeRoot()
    g = root.findGroup(GROUP) or root.insertGroup(0, GROUP)
    QgsProject.instance().addMapLayer(lyr, False)
    g.insertLayer(0, lyr)
    return lyr


def features_of(layer, selected_only):
    return layer.getSelectedFeatures() if selected_only else layer.getFeatures()
