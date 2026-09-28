from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm, QgsProcessingException,
                       QgsProcessingParameterBand,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterRasterDestination,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterString)

from ..author import CREDIT
from ..core import pipeline
from .aoi import read_points, union_geometry


class BathymetrySDB(QgsProcessingAlgorithm):
    METHOD_KEYS = ["stumpf_bg", "stumpf_br", "stumpf_sw", "lyzenga", "rf"]
    METHOD_LABELS = ["Stumpf blue/green (clearer, deeper water)",
                     "Stumpf blue/red (very shallow, somewhat turbid)",
                     "Stumpf switching: blue/red shallow, blue/green deeper",
                     "Lyzenga multiband",
                     "Random Forest (needs scikit-learn)"]
    CONVENTIONS = ["Depth, positive down", "Elevation, negative down"]

    def createInstance(self):
        return BathymetrySDB()

    def name(self):
        return "sdb_compare"

    def displayName(self):
        return "Bathymetry: Stumpf, Lyzenga, Random Forest"

    def group(self):
        return "3. Bathymetry"

    def groupId(self):
        return "bathymetry"

    def shortHelpString(self):
        return (
            CREDIT + "\n\n" +
            "Satellite-derived bathymetry calibrated with your depth points. Methods: "
            "Stumpf log-ratio (blue/green, blue/red), Lyzenga multiband linear model and "
            "Random Forest.\n\n"
            "Stumpf optical depth limit: pSDB is fitted against depth with one line and with a "
            "two-segment line; if the second segment is much flatter (and the BIC prefers it), the "
            "breakpoint is the depth where the ratio saturates. Only shallower points calibrate, and "
            "deeper predictions are flagged in the trust raster.\n\n"
            "Switching: blue/red in very shallow water, blue/green deeper, blended linearly; the switch "
            "is decided with the blue/green depth. Automatic blend: 50 % to 80 % of the blue/red depth "
            "limit.\n\n"
            "Validation: one split for every method; each method is validated on the points common to "
            "all methods and on its own points, with the depth distribution of each sample.\n\n"
            "Lyzenga uses ln(R - R_inf) of the chosen bands (default blue and green; the "
            "red band is attenuated within a few metres and mainly useful in very shallow "
            "water). R_inf is the mean minus k standard deviations "
            "(k = 2 by default) inside the optional deep-water polygon; without it R_inf = 0 (a simplification). With "
            "R_inf, pixels where R <= R_inf (often the red band beyond a few metres) are "
            "invalid, and those points are dropped for every method. The report lists how "
            "many points each method loses on its own.\n\n"
            "Random Forest needs scikit-learn in the QGIS Python; if it is missing the "
            "method is skipped with a warning. It cannot predict outside the calibrated "
            "depth range, and with few points it overfits easily.\n\n"
            "Tide / datum: 'Water level above the points datum' is the height of the "
            "water surface over the vertical datum of your points at the image "
            "acquisition time. It is added to the depths so they match the image.\n\n"
            "All selected methods use exactly the same calibration and validation points, "
            "so they can be compared fairly.\n\n"
            "Validation: 'spatial blocks' keeps whole squares of the chosen size out of "
            "the fit. A random split usually gives better looking but less honest numbers, "
            "because nearby points look alike.\n\n"
            "Trust raster: 1 = inside the calibrated pSDB and depth ranges, "
            "0 = extrapolated, 255 = no data. The Stumpf ratio saturates in deep or "
            "turbid water, so extrapolated pixels deserve suspicion.\n\n"
            "Random Forest uncertainty: optional raster with the standard deviation of the tree "
            "predictions per pixel. It is a relative measure; the report checks how many validation "
            "errors fall within 1 and 2 sd.\n\n"
            "Output sign: depths can be written as positive down or as elevation "
            "(negative down), e.g. to merge with a land DEM. Metrics are always in depth.\n\n"
            "Outputs: one depth band and one trust band per method, an HTML report and a "
            "CSV with every point, its set (cal/val) and predictions.")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer("INPUT", "Reflectance raster"))
        self.addParameter(QgsProcessingParameterBand("BLUE", "Blue band", 1, "INPUT"))
        self.addParameter(QgsProcessingParameterBand("GREEN", "Green band", 2, "INPUT"))
        self.addParameter(QgsProcessingParameterBand("RED", "Red band", 3, "INPUT"))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "POINTS", "Depth points", [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterField(
            "DEPTH_FIELD", "Depth field", parentLayerParameterName="POINTS",
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterEnum("CONVENTION", "Depth sign convention",
                                                     self.CONVENTIONS, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            "TIDE", "Water level above the points datum at acquisition (m)",
            QgsProcessingParameterNumber.Double, 0.0))
        self.addParameter(QgsProcessingParameterField(
            "TIDE_FIELD", "Water level per point (field, optional; overrides the constant)",
            parentLayerParameterName="POINTS", type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterString(
            "DATUM", "Vertical datum of the points (text for the report and metadata)", "", optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            "METHODS", "Methods", self.METHOD_LABELS, allowMultiple=True, defaultValue=[0, 1, 2, 3]))
        self.addParameter(QgsProcessingParameterBoolean(
            "SATURATION", "Stumpf: detect the optical depth limit and calibrate only with shallower points", True))
        self.addParameter(QgsProcessingParameterNumber(
            "SW_START", "Switching: start of the blend (m, 0 = automatic)",
            QgsProcessingParameterNumber.Double, 0.0, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            "SW_END", "Switching: end of the blend (m, 0 = automatic)",
            QgsProcessingParameterNumber.Double, 0.0, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            "RINF_K", "Lyzenga R_inf = deep-water mean minus k standard deviations, k =",
            QgsProcessingParameterNumber.Double, 2.0, minValue=0, maxValue=5))
        self.addParameter(QgsProcessingParameterEnum(
            "LYZ_BANDS", "Lyzenga bands", ["Blue", "Green", "Red"], allowMultiple=True,
            defaultValue=[0, 1]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "DEEP", "Deep-water polygon for Lyzenga R_inf", [QgsProcessing.TypeVectorPolygon],
            optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            "RF_TREES", "Random Forest trees", QgsProcessingParameterNumber.Integer, 300,
            minValue=10, maxValue=5000))
        self.addParameter(QgsProcessingParameterNumber(
            "N_CONST", "Constant n", QgsProcessingParameterNumber.Double, 1000.0, minValue=1))
        self.addParameter(QgsProcessingParameterEnum(
            "WINDOW", "Sampling at each point", ["Single pixel", "3x3 median"], defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            "AGGREGATE", "Average points that fall in the same pixel", True))
        self.addParameter(QgsProcessingParameterEnum(
            "SPLIT", "Calibration/validation split", ["Spatial blocks", "Random"], defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            "BLOCK", "Block size (raster CRS units, usually m)",
            QgsProcessingParameterNumber.Double, 500.0, minValue=1))
        self.addParameter(QgsProcessingParameterNumber(
            "VAL_FRAC", "Validation fraction", QgsProcessingParameterNumber.Double, 0.3,
            minValue=0.05, maxValue=0.9))
        self.addParameter(QgsProcessingParameterNumber(
            "SEED", "Random seed", QgsProcessingParameterNumber.Integer, 42))
        self.addParameter(QgsProcessingParameterString(
            "BINS", "Depth range edges for the report (m)", "0,2,5,10,15,20"))
        self.addParameter(QgsProcessingParameterEnum(
            "OUT_SIGN", "Output sign", self.CONVENTIONS, defaultValue=0))
        self.addParameter(QgsProcessingParameterRasterDestination("OUT_DEPTH", "Depth"))
        self.addParameter(QgsProcessingParameterRasterDestination("OUT_TRUST", "Trust"))
        self.addParameter(QgsProcessingParameterRasterDestination(
            "OUT_SD", "Random Forest uncertainty (sd between trees)", optional=True, createByDefault=False))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUT_REPORT", "Report", "HTML files (*.html)"))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUT_POINTS", "Points table", "CSV files (*.csv)"))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsRasterLayer(parameters, "INPUT", context)
        idx = {k.lower(): self.parameterAsInt(parameters, k, context) for k in ("BLUE", "GREEN", "RED")}

        source = self.parameterAsSource(parameters, "POINTS", context)
        field = self.parameterAsString(parameters, "DEPTH_FIELD", context)
        sign = -1.0 if self.parameterAsEnum(parameters, "CONVENTION", context) == 1 else 1.0
        tide = self.parameterAsDouble(parameters, "TIDE", context)
        tide_field = self.parameterAsString(parameters, "TIDE_FIELD", context) or None
        xs, ys, depths, skipped, fallback = read_points(source.getFeatures(), source.sourceCrs(), layer.crs(),
                                                        context.transformContext(), field, sign, tide, tide_field)
        if fallback:
            feedback.pushWarning(f"{fallback} points without a water level value used the constant {tide} m.")
        if skipped:
            feedback.pushWarning(f"{skipped} points without geometry or depth value were skipped.")
        if len(xs) < 10:
            raise QgsProcessingException("Fewer than 10 usable points.")

        methods = [self.METHOD_KEYS[i] for i in self.parameterAsEnums(parameters, "METHODS", context)]
        if not methods:
            raise QgsProcessingException("Pick at least one method.")
        deep_wkt = None
        deep_src = self.parameterAsSource(parameters, "DEEP", context)
        if deep_src is not None and "lyzenga" in methods:
            deep_wkt = union_geometry(deep_src, layer.crs(), context, feedback).asWkt()
        try:
            edges = [float(s) for s in self.parameterAsString(parameters, "BINS", context).split(",") if s.strip()]
        except ValueError:
            raise QgsProcessingException("Depth range edges must be numbers separated by commas.")

        opts = dict(
            methods=methods,
            lyzenga_bands=[("blue", "green", "red")[i] for i in
                           sorted(self.parameterAsEnums(parameters, "LYZ_BANDS", context))],
            rf_trees=self.parameterAsInt(parameters, "RF_TREES", context),
            n_const=self.parameterAsDouble(parameters, "N_CONST", context),
            window=3 if self.parameterAsEnum(parameters, "WINDOW", context) == 1 else 1,
            aggregate=self.parameterAsBool(parameters, "AGGREGATE", context),
            split="blocks" if self.parameterAsEnum(parameters, "SPLIT", context) == 0 else "random",
            block_size=self.parameterAsDouble(parameters, "BLOCK", context),
            val_fraction=self.parameterAsDouble(parameters, "VAL_FRAC", context),
            seed=self.parameterAsInt(parameters, "SEED", context),
            bin_edges=edges,
            saturation_limit=self.parameterAsBool(parameters, "SATURATION", context),
            switch_range=self._switch(parameters, context),
        )
        out_sign = -1.0 if self.parameterAsEnum(parameters, "OUT_SIGN", context) == 1 else 1.0
        settings = settings_table(layer.source(), source.sourceName(), field, sign, tide, opts)
        water = f"field '{tide_field}' (constant {tide} m where empty)" if tide_field else f"{tide} m (constant)"
        out = {k: (self.parameterAsOutputLayer(parameters, k, context) if k in ("OUT_DEPTH", "OUT_TRUST", "OUT_SD")
                   else self.parameterAsFileOutput(parameters, k, context))
               for k in ("OUT_DEPTH", "OUT_TRUST", "OUT_SD", "OUT_REPORT", "OUT_POINTS")}

        def log(msg, warn=False):
            (feedback.pushWarning if warn else feedback.pushInfo)(msg)

        try:
            pipeline.bathymetry_file(
                layer.source(), idx, xs, ys, depths, opts, deep_wkt=deep_wkt, out_sign=out_sign,
                out_depth=out["OUT_DEPTH"], out_trust=out["OUT_TRUST"],
                out_report=out["OUT_REPORT"], out_points=out["OUT_POINTS"],
                settings=settings, credit=CREDIT, log=log,
                k_sigma=self.parameterAsDouble(parameters, "RINF_K", context),
                datum=self.parameterAsString(parameters, "DATUM", context), water_level=water,
                out_sd=out["OUT_SD"] or None)
        except ValueError as e:
            raise QgsProcessingException(str(e))
        if not out["OUT_SD"]:
            out.pop("OUT_SD")
        return out

    def _switch(self, parameters, context):
        a = self.parameterAsDouble(parameters, "SW_START", context)
        b = self.parameterAsDouble(parameters, "SW_END", context)
        if a <= 0 or b <= 0:
            return None
        if b <= a:
            raise QgsProcessingException("Switching: the end of the blend must be deeper than the start.")
        return (a, b)


def settings_table(raster, points, field, sign, tide, opts):
    return [("Raster", raster), ("Points", points), ("Depth field", field),
            ("Input sign", "depth, positive down" if sign > 0 else "elevation, negative down"),
            ("Water level added (m)", tide), ("Stumpf n", opts["n_const"]),
            ("Lyzenga bands", ", ".join(opts["lyzenga_bands"]) or "-"),
            ("Sampling", "3x3 median" if opts["window"] == 3 else "single pixel"),
            ("Aggregate per pixel", opts["aggregate"]),
            ("Split", "spatial blocks of %g m" % opts["block_size"] if opts["split"] == "blocks" else "random"),
            ("Validation fraction", opts["val_fraction"]), ("Seed", opts["seed"]),
            ("Stumpf optical depth limit", "detected" if opts.get("saturation_limit", True) else "off"),
            ("Switching blend", "automatic" if not opts.get("switch_range") else "%g to %g m" % tuple(opts["switch_range"]))]
