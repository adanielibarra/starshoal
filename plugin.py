import os

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon

try:
    from qgis.PyQt.QtWidgets import QAction, QMenu
except ImportError:  # Qt6
    from qgis.PyQt.QtGui import QAction
    from qgis.PyQt.QtWidgets import QMenu

from .provider import StarShoalProvider

NAME = "StarShoal"
# (translation key, tab index) for the menu entries
ENTRIES = (("tab.download", 1), ("tab.prepare", 2), ("tab.deglint", 3), ("tab.bathy", 4))


class StarShoalPlugin:
    """Own menu in the menu bar (before Help), own toolbar, an entry in Raster,
    and the Processing tools for models and batch runs."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.menu = None
        self.toolbar = None
        self.tab_actions = []
        self.dialog = None

    def initProcessing(self):
        self.provider = StarShoalProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        from .gui import i18n
        i18n.set_lang(i18n.default_lang())
        self.initProcessing()
        mw = self.iface.mainWindow()
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, NAME, mw)
        self.action.setObjectName("StarShoalOpen")
        self.action.triggered.connect(lambda: self.run(0))

        self.menu = QMenu(NAME, mw)
        self.menu.setObjectName("mStarShoalMenu")
        self.menu.addAction(self.action)
        self.menu.addSeparator()
        for key, idx in ENTRIES:
            a = QAction(i18n.tr(key), mw)
            a.triggered.connect(lambda _=False, i=idx: self.run(i))
            self.menu.addAction(a)
            self.tab_actions.append(a)
        bar = mw.menuBar()
        help_menu = self.iface.firstRightStandardMenu()
        if help_menu is not None:
            bar.insertMenu(help_menu.menuAction(), self.menu)
        else:
            bar.addMenu(self.menu)

        self.toolbar = self.iface.addToolBar(NAME)
        self.toolbar.setObjectName("StarShoalToolbar")
        self.toolbar.addAction(self.action)
        self.iface.addPluginToRasterMenu(NAME, self.action)

    def run(self, tab=0):
        from .gui.main_dialog import StarShoalDialog
        if self.dialog is None:
            self.dialog = StarShoalDialog(self.iface, self.iface.mainWindow())
        self.dialog.tabs.setCurrentIndex(tab or 0)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def unload(self):
        if self.action:
            self.iface.removePluginRasterMenu(NAME, self.action)
        if self.toolbar:
            self.toolbar.deleteLater()
            self.toolbar = None
        if self.menu:
            self.iface.mainWindow().menuBar().removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None
        self.tab_actions = []
        if self.dialog:
            for t in self.dialog.tasks():
                t.cancel()
            self.dialog.close()
            self.dialog.deleteLater()
            self.dialog = None
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
