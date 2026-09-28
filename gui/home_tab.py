"""Home tab: logos, language selector and instructions."""
import configparser
import os

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                                 QTextBrowser, QVBoxLayout, QWidget)

from ..author import AUTHOR, COAUTHORS
from . import i18n
from .common import Translatable

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
LOGO_HEIGHT = 64


def plugin_version():
    cp = configparser.ConfigParser()
    try:
        cp.read(os.path.join(PLUGIN_DIR, "metadata.txt"), encoding="utf-8")
        return cp.get("general", "version")
    except Exception:
        return "?"


def _person(p, lang):
    links = [f"ORCID <a href='https://orcid.org/{p['orcid']}'>{p['orcid']}</a>"]
    if p.get("scholar"):
        links.append(f"<a href='{p['scholar']}'>Google Scholar</a>")
    if p.get("researchgate"):
        links.append(f"<a href='{p['researchgate']}'>ResearchGate</a>")
    if p.get("github"):
        links.append(f"GitHub <a href='https://github.com/{p['github']}'>{p['github']}</a>")
    mail = f"<br><a href='mailto:{p['email']}'>{p['email']}</a>" if p.get("email") else ""
    return f"<p><b>{p['name']}</b>{mail}<br>{' · '.join(links)}</p>"


def credits_html(lang):
    people = [AUTHOR] + COAUTHORS
    head = "Créditos" if lang == "es" else "Credits"
    made = "Creado en la" if lang == "es" else "Created at the"
    by = "por" if lang == "es" else "by"
    data = ("Datos: contiene datos modificados de Copernicus Sentinel [año de los datos], servidos por el "
            "Copernicus Data Space Ecosystem." if lang == "es" else
            "Data: contains modified Copernicus Sentinel data [year of the data], served by the "
            "Copernicus Data Space Ecosystem.")
    return (f"<h3>{head}</h3><p>{made} {AUTHOR['faculty']}, {AUTHOR['university']}, {by}:</p>"
            + "".join(_person(p, lang) for p in people) + f"<p>{data}</p>")


HTML = {
    "es": """
<h3>Qué es StarShoal</h3>
<p>Batimetría somera desde satélite (SDB): descarga Sentinel-2, prepara la reflectancia y estima la
profundidad calibrando con tus propios puntos de sonda. Compara varios métodos con los
<b>mismos</b> puntos de calibración y validación.</p>
<p><b>Solo funciona en agua clara y somera.</b> Con agua turbia, fondos muy oscuros o mucha
profundidad, el satélite deja de ver el fondo y el resultado no vale.</p>

<h3>Pestaña 1 · Descarga</h3>
<ol>
<li>Zona: una capa de polígonos y/o una extensión (lienzo, capa o rectángulo dibujado).</li>
<li>Fechas, nivel (L2A para el flujo normal) y nubes máximas de la tesela.</li>
<li><i>Buscar escenas</i> no necesita cuenta. Marca las que quieras y <i>Descargar seleccionadas</i>
(necesita cuenta gratuita de Copernicus Data Space, en una configuración de autenticación
<b>Basic</b> de QGIS: así la contraseña no queda escrita en ningún sitio).</li>
<li>Se descarta el duplicado de una misma fecha y tesela, quedándose con el procesado más reciente.</li>
</ol>

<h3>Pestaña 2 · Preparar</h3>
<p>Lee el .zip sin descomprimir, recorta a la zona y escribe un GeoTIFF de 4 bandas de
reflectancia: azul (B02), verde (B03), rojo (B04) y NIR (B08), a 10 m. Aplica el offset de los
productos recientes (baseline 04.00 en adelante). Quita nubes y sombras con SCL y tierra con NDWI.</p>
<p>Para publicar, mejor <b>ACOLITE</b>: descarga el L1C en la pestaña 1, pásalo por ACOLITE (programa
aparte) y elige aquí <i>Salida de ACOLITE</i> con su fichero <code>..._L2R.nc</code>.</p>

<h3>Pestaña 3 · Sunglint</h3>
<p>Corrección de Hedley et al. (2005): con un polígono de agua profunda, ajusta cada banda visible
contra el NIR y resta el brillo del sol. Mira el R² de cada banda en el registro: si es bajo, hay
poco brillo o la muestra no es buena.</p>

<h3>Pestaña 4 · Batimetría</h3>
<ul>
<li><b>Stumpf</b> azul/verde, azul/rojo y <b>combinado</b> (azul/rojo en lo muy somero, azul/verde
más hondo), <b>Lyzenga</b> multibanda (azul y verde por defecto) y <b>Random Forest</b> (si
scikit-learn está instalado).</li>
<li><b>Límite de profundidad óptica</b>: en Stumpf se busca dónde deja de crecer el cociente y se
calibra solo por encima; lo más hondo queda marcado como extrapolado.</li>
<li>Validación por <b>bloques espaciales</b>, con un solo reparto para todos los métodos. Cada método
se valida con los puntos <b>comunes</b> a todos y con los <b>suyos</b>, y el informe da la
profundidad de cada muestra.</li>
<li>Nivel del agua constante o por punto, y datum vertical escrito en el informe y en el ráster.</li>
<li>Salidas: profundidad y confianza por método (1 = dentro de lo calibrado, 0 = extrapolado),
informe HTML y CSV con cada punto y su predicción.</li>
<li>Se puede guardar como profundidad positiva o como cota negativa, para unir con un MDT de tierra.</li>
</ul>

<h3>Limitaciones</h3>
<ul>
<li>La fecha de la imagen debe estar cerca de la de las sondas: los fondos de arena se mueven.</li>
<li>Con pocos puntos (menos de unos 30 de validación) las métricas son frágiles.</li>
<li>Los tipos de fondo (pradera, arena, fango) cambian la señal y ningún método de aquí los separa.</li>
<li>Probado con datos sintéticos y en QGIS 3.34; no probado aún contra los servidores reales.</li>
</ul>
<p>Todas las herramientas están también en la caja de Processing (StarShoal), para usarlas en
modelos o por lotes.</p>
""",
    "en": """
<h3>What StarShoal is</h3>
<p>Satellite-derived bathymetry (SDB) for shallow water: it downloads Sentinel-2, prepares the
reflectance and estimates depth calibrated with your own sounding points. It compares several
methods on the <b>same</b> calibration and validation points.</p>
<p><b>It only works in clear, shallow water.</b> With turbid water, very dark bottoms or large
depths the satellite no longer sees the bottom and the result is not valid.</p>

<h3>Tab 1 · Download</h3>
<ol>
<li>Area: a polygon layer and/or an extent (canvas, layer or drawn rectangle).</li>
<li>Dates, level (L2A for the standard path) and maximum tile cloud cover.</li>
<li><i>Search scenes</i> needs no account. Tick the ones you want and <i>Download selected</i>
(needs a free Copernicus Data Space account, stored in a QGIS <b>Basic</b> authentication
configuration so the password is not written anywhere).</li>
<li>Duplicates of the same date and tile are removed, keeping the newest processing.</li>
</ol>

<h3>Tab 2 · Prepare</h3>
<p>Reads the zip without unzipping, clips it to the area and writes a 4-band reflectance GeoTIFF:
blue (B02), green (B03), red (B04) and NIR (B08) at 10 m. Applies the offset of recent products
(baseline 04.00 onwards). Removes clouds and shadows with SCL and land with NDWI.</p>
<p>For publication, better use <b>ACOLITE</b>: download the L1C in tab 1, run ACOLITE (a separate
program) and choose <i>ACOLITE output</i> here with its <code>..._L2R.nc</code> file.</p>

<h3>Tab 3 · Sunglint</h3>
<p>Hedley et al. (2005) correction: with a deep-water polygon it fits each visible band against
NIR and removes the glint. Check each band's R² in the log: if it is low there is little glint or
the sample is not good.</p>

<h3>Tab 4 · Bathymetry</h3>
<ul>
<li><b>Stumpf</b> blue/green, blue/red and <b>switching</b> (blue/red in very shallow water,
blue/green deeper), <b>Lyzenga</b> multiband (blue and green by default) and <b>Random Forest</b>
(if scikit-learn is installed).</li>
<li><b>Optical depth limit</b>: for Stumpf, where the ratio stops growing; only shallower points
calibrate and deeper pixels are flagged as extrapolated.</li>
<li>Validation with <b>spatial blocks</b>, one split for every method. Each method is validated on
the points <b>common</b> to all and on its <b>own</b> points, with the depths of each sample.</li>
<li>Water level constant or per point; vertical datum written in the report and the raster.</li>
<li>Outputs: depth and trust per method (1 = inside the calibrated range, 0 = extrapolated), an
HTML report and a CSV with every point and its prediction.</li>
<li>Can be saved as positive depth or negative elevation, to merge with a land DEM.</li>
</ul>

<h3>Limitations</h3>
<ul>
<li>The image date should be close to the survey date: sandy bottoms move.</li>
<li>With few points (fewer than about 30 for validation) the metrics are fragile.</li>
<li>Bottom types (seagrass, sand, mud) change the signal and no method here separates them.</li>
<li>Tested with synthetic data and in QGIS 3.34; not yet tested against the real servers.</li>
</ul>
<p>Every tool is also in the Processing Toolbox (StarShoal), for models or batch runs.</p>
""",
}


class HomeTab(QWidget, Translatable):
    languageChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        # logos on a white strip: the official logos are made for a light background
        strip = QFrame()
        strip.setObjectName("ssLogoStrip")
        strip.setStyleSheet("#ssLogoStrip { background: white; border-radius: 6px; }")
        hl = QHBoxLayout(strip)
        hl.setContentsMargins(16, 10, 16, 10)
        hl.setSpacing(28)
        hl.addStretch()
        for name in ("starshoal.png", "uat.png", "fic.png"):
            lab = QLabel()
            pm = QPixmap(os.path.join(PLUGIN_DIR, "about", name))
            if not pm.isNull():
                lab.setPixmap(pm.scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))
            else:
                lab.setText(name.split(".")[0].upper())
            hl.addWidget(lab)
        hl.addStretch()
        lay.addWidget(strip)

        head = QHBoxLayout()
        tbox = QVBoxLayout()
        tbox.addWidget(QLabel("<span style='font-size:18pt; font-weight:600'>StarShoal</span>"))
        self.subtitle = QLabel()
        self._t(self.subtitle.setText, "home.subtitle")
        self.version = QLabel()
        self._t(self.version.setText, "home.version", plugin_version())
        tbox.addWidget(self.subtitle)
        tbox.addWidget(self.version)
        head.addLayout(tbox)
        head.addStretch()
        head.addWidget(self._lbl("home.language"))
        self.cb_lang = QComboBox()
        for code, name in i18n.LANGS.items():
            self.cb_lang.addItem(name, code)
        self.cb_lang.setCurrentIndex(self.cb_lang.findData(i18n.lang()))
        self.cb_lang.currentIndexChanged.connect(self._lang_changed)
        head.addWidget(self.cb_lang)
        lay.addLayout(head)

        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        lay.addWidget(self.text, 1)
        self._retranslate_extra()

    def _lang_changed(self):
        code = self.cb_lang.currentData()
        i18n.set_lang(code)
        try:
            i18n.save_lang(code)
        except Exception as e:  # not being able to remember the language is not fatal
            from qgis.core import Qgis, QgsMessageLog
            QgsMessageLog.logMessage(f"Could not save the language: {e}", "StarShoal", Qgis.MessageLevel.Info)
        self.languageChanged.emit(code)

    def _retranslate_extra(self):
        self.text.setHtml(HTML[i18n.lang()] + credits_html(i18n.lang()))
        idx = self.cb_lang.findData(i18n.lang())
        if idx != self.cb_lang.currentIndex():
            self.cb_lang.blockSignals(True)
            self.cb_lang.setCurrentIndex(idx)
            self.cb_lang.blockSignals(False)
