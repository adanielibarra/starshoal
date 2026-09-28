# StarShoal

Satellite-derived bathymetry (SDB) for QGIS. One window with tabs (menu *StarShoal*,
its toolbar button, or *Raster > StarShoal*), in Spanish and English. Every tool is
also in the Processing Toolbox for models and batch runs.

Tabs (version 1.0.0):

1. **Download Sentinel-2** from the Copernicus Data Space Ecosystem (free account).
2. **Prepare**: Sentinel-2 L2A (Sen2Cor) or an **ACOLITE** output (L2R NetCDF or
   its exported GeoTIFFs), clipped by extent and/or polygon, with SCL cloud mask
   (L2A only) and NDWI water mask.
3. **Sunglint correction (Hedley)** from a deep-water sample polygon.
4. **Bathymetry**: Stumpf (blue/green, blue/red and a blue/red to blue/green
   switching model), Lyzenga multiband and Random Forest. Stumpf ratios get an
   optical depth limit where pSDB stops growing. One calibration/validation split
   (spatial blocks); every method is validated on the points common to all and on
   its own points. Water level constant or per point, vertical datum written in the
   report and the raster metadata. Random Forest also gives a per-pixel uncertainty
   (spread between trees) whose coverage is checked on the validation points.
   Output as depth or elevation, HTML report + CSV.

Not yet: running ACOLITE from the plugin, Landsat, ICESat-2.

Random Forest needs scikit-learn in the QGIS Python (on Windows, install it from
the OSGeo4W Shell with `python -m pip install scikit-learn`). Without it the
method is skipped with a warning.

## Install (development)

Copy the `starshoal` folder into your QGIS profile plugins folder
(`Settings > User Profiles > Open Active Profile Folder > python/plugins`),
restart QGIS and enable it in the Plugin Manager. The tools appear in the
Processing Toolbox under *StarShoal*.

## CDSE credentials

`Settings > Options > Authentication`, add a configuration of type **Basic**
with your CDSE username and password, and choose it in the download tool.

## Dependencies

Only what QGIS already ships: GDAL and numpy.

## Tests

`python -m pytest tests` from the plugin folder (the tests live in the source
repository; the plugin zip does not ship them). The QGIS tests are skipped when
QGIS is not importable.

## Authors

Daniel Ibarra-Marinas, Facultad de Ingeniería y Ciencias, Universidad Autónoma de Tamaulipas.
daniel.ibarra@uat.edu.mx · ORCID 0000-0003-3683-4456

Ana Mónica de Jhesú García, Facultad de Ingeniería y Ciencias, Universidad Autónoma de Tamaulipas.
ORCID 0000-0001-6613-6945

## License

GPL-2.0-or-later (see `LICENSE`).
