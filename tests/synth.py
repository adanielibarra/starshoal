"""Synthetic scenes and Sentinel-2 L2A zips for the tests (no real data)."""
import os
import zipfile

import numpy as np

K = {"B02": 0.05, "B03": 0.09, "B04": 0.45}       # attenuation-like coefficients (1/m)
R_DEEP = {"B02": 0.012, "B03": 0.008, "B04": 0.002}
R_BOTTOM = {"B02": 0.08, "B03": 0.10, "B04": 0.09}
GT = (600000.0, 10.0, 0.0, 4200000.0, 0.0, -10.0)   # UTM 30N, 10 m
EPSG = 32630


def reflectance(depth):
    """Two-flow-like model: R = R_deep + (R_bottom - R_deep) exp(-2 K z)."""
    return {b: R_DEEP[b] + (R_BOTTOM[b] - R_DEEP[b]) * np.exp(-2 * K[b] * depth) for b in K}


def ramp(h=300, w=300, zmax=30.0, noise=0.01, seed=1):
    """Depth ramp from 0.5 m (left) to zmax (right) and its noisy reflectance."""
    rng = np.random.default_rng(seed)
    depth = np.tile(np.linspace(0.5, zmax, w), (h, 1))
    r = reflectance(depth)
    bands = {"blue": r["B02"], "green": r["B03"], "red": r["B04"]}
    for k in bands:
        bands[k] = bands[k] * (1 + rng.normal(0, noise, (h, w)))
    return depth, bands


def points(depth, n=400, seed=2, max_col=None, sd=0.2):
    """Random points (x, y, depth + noise) over a depth grid with GT."""
    rng = np.random.default_rng(seed)
    h, w = depth.shape
    c = rng.integers(0, max_col or w, n)
    r = rng.integers(0, h, n)
    xs = GT[0] + (c + 0.5) * GT[1]
    ys = GT[3] + (r + 0.5) * GT[5]
    return xs, ys, depth[r, c] + rng.normal(0, sd, n)


def l2a_zip(folder, h=200, w=200, zmax=25.0, offset=-1000, cloud_box=(80, 90, 50, 60), land_cols=10):
    """Write a fake Sentinel-2 L2A zip (GeoTIFFs named .jp2, GDAL reads them by content)."""
    from osgeo import gdal, osr
    depth = np.tile(np.linspace(0.5, zmax, w), (h, 1))
    r = reflectance(depth)
    r["B08"] = np.full((h, w), 0.002)
    r["B08"][:, :land_cols] = 0.3
    r["B03"][:, :land_cols] = 0.08
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(EPSG)
    safe = "S2B_MSIL2A_20250701T105619_N0511_R094_T30SXG_20250701T120000.SAFE"
    g = f"{safe}/GRANULE/L2A_T30SXG_A000_20250701T105619/IMG_DATA"
    path = os.path.join(folder, safe.replace(".SAFE", ".zip"))
    drv = gdal.GetDriverByName("GTiff")
    with zipfile.ZipFile(path, "w") as z:
        for b in ("B02", "B03", "B04", "B08"):
            dn = np.clip(np.round(r[b] * 10000 - offset), 1, 65535).astype(np.uint16)
            tmp = os.path.join(folder, f"{b}.tif")
            d = drv.Create(tmp, w, h, 1, gdal.GDT_UInt16)
            d.SetGeoTransform(GT)
            d.SetProjection(srs.ExportToWkt())
            d.GetRasterBand(1).WriteArray(dn)
            d = None
            z.write(tmp, f"{g}/R10m/T30SXG_20250701T105619_{b}_10m.jp2")
        scl = np.full((h // 2, w // 2), 6, np.uint8)
        r0, r1, c0, c1 = cloud_box
        scl[r0 // 2:r1 // 2, c0 // 2:c1 // 2] = 9
        tmp = os.path.join(folder, "scl.tif")
        d = drv.Create(tmp, w // 2, h // 2, 1, gdal.GDT_Byte)
        d.SetGeoTransform((GT[0], 20.0, 0, GT[3], 0, -20.0))
        d.SetProjection(srs.ExportToWkt())
        d.GetRasterBand(1).WriteArray(scl)
        d = None
        z.write(tmp, f"{g}/R20m/T30SXG_20250701T105619_SCL_20m.jp2")
        xml = ("<x><BOA_QUANTIFICATION_VALUE unit=\"none\">10000</BOA_QUANTIFICATION_VALUE>"
               + "".join(f'<BOA_ADD_OFFSET band_id="{i}">{offset}</BOA_ADD_OFFSET>' for i in range(13)) + "</x>")
        z.writestr(f"{safe}/MTD_MSIL2A.xml", xml)
    return path, depth


ACOLITE_WAVES = (443, 492, 560, 665, 704, 740, 783, 833, 865, 1614, 2202)


def acolite_nc(folder, h=200, w=200, zmax=25.0, name="S2A_MSI_2025_07_01_10_56_19_T30SXG_L2R"):
    """Fake ACOLITE L2R NetCDF written like ACOLITE does for Sentinel-2 (dims y, x; x/y at pixel
    centres; CF grid_mapping from pyproj; rhos_<wave> variables) plus its per-variable GeoTIFFs."""
    import netCDF4
    from osgeo import gdal, osr
    from pyproj import CRS
    depth = np.tile(np.linspace(0.5, zmax, w), (h, 1))
    r = reflectance(depth)
    by_wave = {492: r["B02"], 560: r["B03"], 665: r["B04"]}
    nc = os.path.join(folder, name + ".nc")
    cf = CRS.from_epsg(EPSG).to_cf()
    key = cf["grid_mapping_name"]
    with netCDF4.Dataset(nc, "w") as d:
        d.createDimension("y", h)
        d.createDimension("x", w)
        d.setncattr("projection_key", key)
        pm = d.createVariable(key, "i4")
        for k, v in cf.items():
            pm.setncattr(k, v)
        x = d.createVariable("x", "f8", ("x",))
        y = d.createVariable("y", "f8", ("y",))
        x[:] = GT[0] + (np.arange(w) + 0.5) * GT[1]
        y[:] = GT[3] + (np.arange(h) + 0.5) * GT[5]
        for v, sn in ((x, "projection_x_coordinate"), (y, "projection_y_coordinate")):
            v.standard_name = sn
            v.units = "m"
        for wave in ACOLITE_WAVES:
            a = by_wave.get(wave, np.full((h, w), 0.002 if wave > 700 else 0.01)).astype(np.float32)
            if wave == 492:
                a[:, :10] = np.nan
            var = d.createVariable(f"rhos_{wave}", "f4", ("y", "x"), fill_value=np.float32(np.nan))
            var.grid_mapping = key
            var[:] = a
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(EPSG)
    for wave in ACOLITE_WAVES:   # the optional GeoTIFF export
        gdal.Translate(os.path.join(folder, f"{name}_rhos_{wave}.tif"), f'NETCDF:"{nc}":rhos_{wave}', format="GTiff")
    return nc, depth
