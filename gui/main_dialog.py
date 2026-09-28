"""Single StarShoal window with all tabs."""
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QVBoxLayout

from . import i18n
from .bathy_tab import BathyTab
from .deglint_tab import DeglintTab
from .download_tab import DownloadTab
from .home_tab import HomeTab
from .i18n import tr
from .prepare_tab import PrepareTab

TAB_KEYS = ("tab.home", "tab.download", "tab.prepare", "tab.deglint", "tab.bathy")


class StarShoalDialog(QDialog):
    def __init__(self, iface, parent=None):
        i18n.set_lang(i18n.default_lang())
        super().__init__(parent)
        self.resize(1040, 860)
        self.tabs = QTabWidget()
        self.home = HomeTab(self)
        self.download = DownloadTab(iface, self, self)
        self.prepare = PrepareTab(iface, self, self)
        self.deglint = DeglintTab(self)
        self.bathy = BathyTab(self)
        self.pages = (self.home, self.download, self.prepare, self.deglint, self.bathy)
        for w in self.pages:
            self.tabs.addTab(w, "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.tabs)
        self._titles()

        # each step feeds the next one
        self.home.languageChanged.connect(self._retranslate)
        self.download.downloaded.connect(lambda paths: self.prepare.set_zip(paths[-1]))
        self.download.area.cb_layer.layerChanged.connect(self.prepare.area.cb_layer.setLayer)
        self.prepare.prepared.connect(self.deglint.set_raster)
        self.prepare.prepared.connect(self.bathy.set_raster)
        self.deglint.corrected.connect(self.bathy.set_raster)

    def tasks(self):
        return [p.run.task for p in self.pages[1:] if p.run.task is not None]

    def _titles(self):
        self.setWindowTitle(tr("win.title"))
        for n, key in enumerate(TAB_KEYS):
            self.tabs.setTabText(n, tr(key))

    def _retranslate(self, _code=None):
        self._titles()
        for w in self.pages:
            w.retranslate()
            for child in (getattr(w, "area", None), getattr(w, "rbox", None), getattr(w, "run", None)):
                if child is not None:
                    child.retranslate()
