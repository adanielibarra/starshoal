"""Minimal ES/EN translation table for the StarShoal window (no Qt Linguist).

tr(key, *args) returns the text in the current language. Unknown keys are
returned as they are, so a missing entry is visible but never breaks anything.
"""

LANGS = {"es": "Español", "en": "English"}
_lang = "es"


def set_lang(code):
    global _lang
    _lang = code if code in LANGS else "es"


def lang():
    return _lang


def tr(key, *args):
    entry = STRINGS.get(key)
    text = key if entry is None else entry[0 if _lang == "es" else 1]
    return text % args if args else text


def default_lang():
    """Spanish unless English was chosen in the Home tab."""
    try:
        from qgis.core import QgsSettings
        saved = QgsSettings().value("StarShoal/lang", "")
        return saved if saved in LANGS else "es"
    except Exception:
        return "es"


def save_lang(code):
    from qgis.core import QgsSettings
    QgsSettings().setValue("StarShoal/lang", code)


STRINGS = {
    # window and tabs
    "win.title": ("StarShoal: batimetría desde satélite", "StarShoal: satellite-derived bathymetry"),
    "tab.home": ("Inicio", "Home"),
    "tab.download": ("1 · Descarga", "1 · Download"),
    "tab.prepare": ("2 · Preparar", "2 · Prepare"),
    "tab.deglint": ("3 · Sunglint", "3 · Sunglint"),
    "tab.bathy": ("4 · Batimetría", "4 · Bathymetry"),
    "menu.open": ("Abrir StarShoal", "Open StarShoal"),

    # home
    "home.subtitle": ("Batimetría desde satélite para QGIS", "Satellite-derived bathymetry for QGIS"),
    "home.version": ("Versión %s", "Version %s"),
    "home.language": ("Idioma:", "Language:"),

    # shared
    "c.area": ("Zona", "Area"),
    "c.layer": ("Capa de polígonos:", "Polygon layer:"),
    "c.layer.tip": ("Opcional. Todo lo que quede fuera del polígono se ignora.",
                    "Optional. Everything outside the polygon is ignored."),
    "c.selected": ("Solo los objetos seleccionados", "Selected features only"),
    "c.extent": ("Extensión:", "Extent:"),
    "c.extent.tip": ("Opcional. Lienzo, capa o rectángulo dibujado. Si das también un polígono, se usa la intersección.",
                     "Optional. Canvas, layer or drawn rectangle. With a polygon too, the intersection is used."),
    "c.none": ("(ninguna)", "(none)"),
    "c.output": ("Salida", "Output"),
    "c.outfile": ("Fichero de salida:", "Output file:"),
    "c.outdir": ("Carpeta de salida:", "Output folder:"),
    "c.addmap": ("Añadir al mapa", "Add to the map"),
    "c.run": ("Ejecutar", "Run"),
    "c.cancel": ("Cancelar", "Cancel"),
    "c.busy": ("Ya hay un proceso en marcha en esta pestaña.", "A process is already running in this tab."),
    "c.done": ("Terminado.", "Finished."),
    "c.failed": ("Error: %s", "Error: %s"),
    "c.canceled": ("Cancelado.", "Canceled."),
    "c.raster": ("Ráster de reflectancia:", "Reflectance raster:"),
    "c.blue": ("Banda azul:", "Blue band:"),
    "c.green": ("Banda verde:", "Green band:"),
    "c.red": ("Banda roja:", "Red band:"),
    "c.nir": ("Banda NIR:", "NIR band:"),
    "c.image": ("Imagen", "Image"),
    "c.need.raster": ("Elige un ráster.", "Choose a raster."),
    "c.need.out": ("Elige dónde guardar el resultado.", "Choose where to save the result."),
    "c.nooverlap": ("La extensión y el polígono no se solapan.", "The extent and the polygon do not overlap."),
    "c.nopoly": ("La capa de polígonos no tiene polígonos válidos (o no hay ninguno seleccionado).",
                 "The polygon layer has no valid polygons (or none is selected)."),

    # download
    "dl.search": ("Búsqueda", "Search"),
    "dl.from": ("Desde:", "From:"),
    "dl.to": ("Hasta:", "To:"),
    "dl.level": ("Nivel:", "Level:"),
    "dl.level.l2a": ("L2A (reflectancia de superficie)", "L2A (surface reflectance)"),
    "dl.level.l1c": ("L1C (techo de atmósfera, para ACOLITE)", "L1C (top of atmosphere, for ACOLITE)"),
    "dl.cloud": ("Nubes máx. en la tesela:", "Max tile cloud cover:"),
    "dl.account": ("Cuenta de Copernicus Data Space", "Copernicus Data Space account"),
    "dl.auth": ("Credenciales:", "Credentials:"),
    "dl.auth.help": ("Crea una configuración de tipo <b>Basic</b> (botón +) con tu usuario y contraseña de "
                     "<a href='https://dataspace.copernicus.eu'>dataspace.copernicus.eu</a>. "
                     "La cuenta es gratuita. Buscar no la necesita; descargar sí.",
                     "Create a <b>Basic</b> configuration (+ button) with your "
                     "<a href='https://dataspace.copernicus.eu'>dataspace.copernicus.eu</a> username and "
                     "password. The account is free. Searching does not need it; downloading does."),
    "dl.btn.search": ("Buscar escenas", "Search scenes"),
    "dl.btn.download": ("Descargar seleccionadas", "Download selected"),
    "dl.btn.all": ("Todas", "All"),
    "dl.btn.none": ("Ninguna", "None"),
    "dl.col.date": ("Fecha", "Date"),
    "dl.col.tile": ("Tesela", "Tile"),
    "dl.col.cloud": ("Nubes %", "Cloud %"),
    "dl.col.size": ("MB", "MB"),
    "dl.col.name": ("Producto", "Product"),
    "dl.need.area": ("Da una extensión o una capa de polígonos para buscar.", "Give an extent or a polygon layer to search."),
    "dl.need.dir": ("Elige una carpeta de descarga.", "Choose a download folder."),
    "dl.need.auth": ("Elige una configuración de credenciales de Copernicus.", "Choose a Copernicus credentials configuration."),
    "dl.bad.auth": ("La configuración debe ser de tipo Basic, con usuario y contraseña.",
                    "The configuration must be Basic, with username and password."),
    "dl.need.sel": ("Marca al menos una escena.", "Tick at least one scene."),
    "dl.found": ("%d escenas encontradas (sin duplicados).", "%d scenes found (duplicates removed)."),
    "dl.none": ("No hay escenas. Prueba con más fechas o más nubes.", "No scenes. Try a wider date range or more cloud."),
    "dl.searching": ("Buscando en Copernicus Data Space...", "Searching Copernicus Data Space..."),
    "dl.getting": ("Descargando %d/%d: %s", "Downloading %d/%d: %s"),
    "dl.saved": ("  guardado: %s", "  saved: %s"),
    "dl.total": ("Tamaño total marcado: %.0f MB", "Total ticked size: %.0f MB"),

    # prepare
    "pr.input": ("Imagen de entrada", "Input image"),
    "pr.source": ("Origen:", "Source:"),
    "pr.src.l2a": ("Sentinel-2 L2A de Copernicus (Sen2Cor)", "Sentinel-2 L2A from Copernicus (Sen2Cor)"),
    "pr.src.aco": ("Salida de ACOLITE (NetCDF o GeoTIFF)", "ACOLITE output (NetCDF or GeoTIFF)"),
    "pr.zip": ("Fichero:", "File:"),
    "pr.quantity": ("Magnitud:", "Quantity:"),
    "pr.quantity.tip": ("rhos: reflectancia de superficie (L2R), la habitual. rhow y Rrs solo si el fichero L2W las trae.",
                        "rhos: surface reflectance (L2R), the usual one. rhow and Rrs only if the L2W file has them."),
    "pr.aco.help": ("ACOLITE es un programa aparte (RBINS, GPL-3). Pásalo sobre un Sentinel-2 L1C (descárgalo en la "
                    "pestaña 1 con nivel L1C) y trae aquí su ..._L2R.nc. No hay máscara de nubes: deja las nubes fuera "
                    "con el polígono. Su corrección de brillo viene desactivada por defecto; si no la activaste, usa la pestaña 3.",
                    "ACOLITE is a separate program (RBINS, GPL-3). Run it on a Sentinel-2 L1C (download it in tab 1 with "
                    "level L1C) and bring here its ..._L2R.nc. There is no cloud mask: leave clouds out with the polygon. "
                    "Its glint correction is off by default; if you did not turn it on, use tab 3."),
    "pr.need.aco": ("Elige un NetCDF de ACOLITE (.nc) o uno de sus GeoTIFF exportados.",
                    "Choose an ACOLITE NetCDF (.nc) or one of its exported GeoTIFFs."),
    "pr.vars": ("Variables usadas: %s", "Variables used: %s"),
    "pr.zip.tip": ("Tal como se descarga, sin descomprimir.", "As downloaded, no need to unzip."),
    "pr.masks": ("Máscaras", "Masks"),
    "pr.scl": ("Quitar nubes y sombras con SCL", "Remove clouds and shadows with SCL"),
    "pr.scl.tip": ("Ojo: SCL puede marcar como nube fondos someros muy claros (arena blanca). Compruébalo en tu zona.",
                   "Careful: SCL can label very bright shallow bottoms (white sand) as cloud. Check it on your site."),
    "pr.ndwi": ("Quitar tierra con NDWI, umbral:", "Remove land with NDWI, threshold:"),
    "pr.need.zip": ("Elige un fichero .zip de Sentinel-2 L2A.", "Choose a Sentinel-2 L2A zip file."),
    "pr.whole": ("Sin extensión ni polígono: se procesa la tesela entera (unos 110 x 110 km).",
                 "No extent or polygon: the whole tile is processed (about 110 x 110 km)."),
    "pr.stats": ("Píxeles: %d. Fuera del polígono: %d. Nubes/sombras: %d. Tierra: %d. Agua útil: %d.",
                 "Pixels: %d. Outside the polygon: %d. Cloud/shadow: %d. Land: %d. Usable water: %d."),

    # deglint
    "dg.deep": ("Muestra de agua profunda", "Deep-water sample"),
    "dg.deep.layer": ("Polígono de agua profunda:", "Deep-water polygon:"),
    "dg.deep.help": ("Agua donde no se vea el fondo y con algo de brillo del sol. Tiene que caer dentro del ráster. "
                     "Si tu zona no tiene agua profunda, prepara antes una extensión mayor.",
                     "Water where the bottom is not visible, with some sunglint. It must fall inside the raster. "
                     "If your area has no deep water, prepare a larger extent first."),
    "dg.pct": ("Percentil de referencia del NIR (0 = mínimo):", "NIR reference percentile (0 = minimum):"),
    "dg.need.deep": ("Elige el polígono de agua profunda.", "Choose the deep-water polygon."),

    # bathymetry
    "ba.points": ("Puntos de profundidad", "Depth points"),
    "ba.pts": ("Capa de puntos:", "Point layer:"),
    "ba.field": ("Campo de profundidad:", "Depth field:"),
    "ba.sign": ("Los valores son:", "Values are:"),
    "ba.sign.depth": ("Profundidad, positiva hacia abajo", "Depth, positive down"),
    "ba.sign.elev": ("Cota, negativa hacia abajo", "Elevation, negative down"),
    "ba.tide": ("Nivel del agua sobre el datum:", "Water level above datum:"),
    "ba.tide.tip": ("Altura de la superficie del agua sobre el datum vertical de tus puntos en el momento de la imagen. "
                    "Se suma a las profundidades.",
                    "Height of the water surface over the vertical datum of your points at the image time. "
                    "It is added to the depths."),
    "ba.methods": ("Métodos", "Methods"),
    "ba.m.stumpf_bg": ("Stumpf azul/verde", "Stumpf blue/green"),
    "ba.m.stumpf_br": ("Stumpf azul/rojo", "Stumpf blue/red"),
    "ba.m.stumpf_sw": ("Stumpf combinado (azul/rojo → azul/verde)", "Stumpf switching (blue/red → blue/green)"),
    "ba.m.lyzenga": ("Lyzenga multibanda", "Lyzenga multiband"),
    "ba.sat": ("Stumpf: detectar el límite de profundidad óptica", "Stumpf: detect the optical depth limit"),
    "ba.sat.tip": ("Busca dónde deja de crecer el cociente con la profundidad y calibra solo con los puntos "
                   "menos profundos. Lo más hondo queda marcado como extrapolado.",
                   "Finds where the ratio stops growing with depth and calibrates only with shallower points. "
                   "Deeper pixels are flagged as extrapolated."),
    "ba.sw": ("Mezcla del combinado (m):", "Switching blend (m):"),
    "ba.sw.tip": ("Por debajo del primer valor, azul/rojo; por encima del segundo, azul/verde; en medio, mezcla. "
                  "0 y 0 = automático (50 % y 80 % del límite de azul/rojo).",
                  "Below the first value, blue/red; above the second, blue/green; in between, a blend. "
                  "0 and 0 = automatic (50 % and 80 % of the blue/red limit)."),
    "ba.auto": ("auto", "auto"),
    "ba.k": ("R∞ = media − k·σ, k:", "R_inf = mean − k·sd, k:"),
    "ba.tidefield": ("Nivel del agua por punto (campo):", "Water level per point (field):"),
    "ba.tidefield.tip": ("Opcional. Si el punto tiene valor, sustituye al nivel constante.",
                         "Optional. When the point has a value, it replaces the constant level."),
    "ba.datum": ("Datum vertical:", "Vertical datum:"),
    "ba.datum.tip": ("Texto libre (NMM Alicante, LAT, cero hidrográfico...). Se escribe en el informe y en los metadatos del ráster.",
                     "Free text (MSL, LAT, chart datum...). Written in the report and in the raster metadata."),
    "ba.datum.ph": ("p. ej. NMM Alicante", "e.g. MSL"),
    "ba.fallback": ("%d puntos sin nivel del agua usan el valor constante.", "%d points without a water level use the constant value."),
    "ba.col.limit": ("Límite (m)", "Limit (m)"),
    "ba.col.nc": ("n común", "Common n"),
    "ba.col.rc": ("RMSE común", "Common RMSE"),
    "ba.col.no": ("n propio", "Own n"),
    "ba.col.ro": ("RMSE propio", "Own RMSE"),
    "ba.col.bo": ("Sesgo propio", "Own bias"),
    "ba.col.ri": ("RMSE ≤ límite", "RMSE ≤ limit"),
    "ba.m.rf": ("Random Forest (con scikit-learn)", "Random Forest (with scikit-learn)"),
    "ba.lyz.bands": ("Bandas de Lyzenga:", "Lyzenga bands:"),
    "ba.b.blue": ("azul", "blue"),
    "ba.b.green": ("verde", "green"),
    "ba.b.red": ("rojo", "red"),
    "ba.deep": ("Agua profunda (R∞):", "Deep water (R_inf):"),
    "ba.deep.tip": ("Opcional. Polígono de agua profunda para el R∞ de Lyzenga; sin él, R∞ = 0.",
                    "Optional. Deep-water polygon for the Lyzenga R_inf; without it, R_inf = 0."),
    "ba.trees": ("Árboles de Random Forest:", "Random Forest trees:"),
    "ba.n": ("Constante n de Stumpf:", "Stumpf constant n:"),
    "ba.val": ("Calibración y validación", "Calibration and validation"),
    "ba.split": ("Separación:", "Split:"),
    "ba.split.blocks": ("Bloques espaciales", "Spatial blocks"),
    "ba.split.random": ("Al azar", "Random"),
    "ba.block": ("Tamaño de bloque:", "Block size:"),
    "ba.valfrac": ("Fracción de validación:", "Validation fraction:"),
    "ba.seed": ("Semilla:", "Seed:"),
    "ba.window": ("Muestreo en cada punto:", "Sampling at each point:"),
    "ba.window.1": ("Un píxel", "Single pixel"),
    "ba.window.3": ("Mediana 3x3", "3x3 median"),
    "ba.aggregate": ("Promediar puntos del mismo píxel", "Average points in the same pixel"),
    "ba.bins": ("Tramos del informe (m):", "Report depth ranges (m):"),
    "ba.outsign": ("Guardar como:", "Save as:"),
    "ba.addtrust": ("Añadir también las capas de confianza", "Also add the trust layers"),
    "ba.results": ("Resultados (validación)", "Results (validation)"),
    "ba.col.method": ("Método", "Method"),
    "ba.col.lost": ("Puntos perdidos", "Points lost"),
    "ba.open": ("Abrir informe", "Open report"),
    "ba.need.pts": ("Elige la capa de puntos y el campo de profundidad.", "Choose the point layer and the depth field."),
    "ba.need.method": ("Marca al menos un método.", "Tick at least one method."),
    "ba.need.lyz": ("Lyzenga necesita al menos una banda.", "Lyzenga needs at least one band."),
    "ba.few": ("Solo hay %d puntos válidos; hacen falta al menos 10.", "Only %d usable points; at least 10 are needed."),
    "ba.skipped": ("%d puntos sin geometría o sin valor se han ignorado.", "%d points without geometry or value were skipped."),
}
