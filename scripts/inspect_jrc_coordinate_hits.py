from pathlib import Path
import rasterio
from pyproj import Transformer

lat, lon = 48.81162111, -3.43762118
for year in (2020, 2021):
    for path in sorted((Path("data/JRC_flood_depth_maps") / str(year)).glob("*.tif")):
        with rasterio.open(path) as ds:
            tr = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True)
            x, y = tr.transform(lon, lat)
            if not (ds.bounds.left <= x <= ds.bounds.right and ds.bounds.bottom <= y <= ds.bounds.top):
                continue
            try:
                value = next(ds.sample([(x, y)]))[0]
            except Exception:
                continue
            nodata = ds.nodata
            if value != nodata and value > 0:
                print(year, value, path.name)
