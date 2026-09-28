import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithms.download_s2 import DownloadSentinel2
from .algorithms.import_acolite import ImportAcolite
from .algorithms.prepare_s2 import PrepareSentinel2
from .algorithms.deglint_hedley import DeglintHedley
from .algorithms.sdb_compare import BathymetrySDB


class StarShoalProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        for alg in (DownloadSentinel2(), PrepareSentinel2(), ImportAcolite(), DeglintHedley(), BathymetrySDB()):
            self.addAlgorithm(alg)

    def id(self):
        return "starshoal"

    def name(self):
        return "StarShoal"

    def longName(self):
        return "StarShoal (Daniel Ibarra-Marinas, UAT)"

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
