from pathlib import Path
import re
import numpy as np
from osgeo import gdal, osr

LAT, LON = 48.81162111, -3.43762118
ROOT = Path("data/JRC_flood_depth_maps")
PATTERN = re.compile(r"WD_MERGE_(\d{4}-\d{2}-\d{2})---(\d{4}-\d{2}-\d{2})_duration_(\d+)_days")

source = osr.SpatialReference()
source.ImportFromEPSG(4326)
source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

for year in (2020, 2021):
    for path in sorted((ROOT / str(year)).glob("*.tif")):
        match = PATTERN.search(path.name)
        if not match:
            continue
        ds = gdal.Open(str(path), gdal.GA_ReadOnly)
        target = osr.SpatialReference(wkt=ds.GetProjection())
        target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source, target)
        x, y, _ = transform.TransformPoint(LON, LAT)
        gt = ds.GetGeoTransform()
        inv = gdal.InvGeoTransform(gt)
        px = int(inv[0] + inv[1] * x + inv[2] * y)
        py = int(inv[3] + inv[4] * x + inv[5] * y)
        if px < 0 or py < 0 or px >= ds.RasterXSize or py >= ds.RasterYSize:
            continue
        pixel_m = max(abs(gt[1]), abs(gt[5]))
        radii = {"point40m": max(1, int(np.ceil(40 / pixel_m))), "area1km": max(1, int(np.ceil(1000 / pixel_m)))}
        results = {}
        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        for label, radius in radii.items():
            x0, y0 = max(0, px-radius), max(0, py-radius)
            x1, y1 = min(ds.RasterXSize, px+radius+1), min(ds.RasterYSize, py+radius+1)
            arr = band.ReadAsArray(x0, y0, x1-x0, y1-y0)
            valid = (arr > 0) & (arr != 9999)
            if nodata is not None:
                valid &= arr != nodata
            results[label] = (int(valid.sum()), float(arr[valid].max()) if valid.any() else 0.0)
        if results["point40m"][0] or results["area1km"][0]:
            print("|".join([match.group(1), match.group(2), match.group(3), str(results["point40m"]), str(results["area1km"]), path.name]))
