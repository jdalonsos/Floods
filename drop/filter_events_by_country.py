"""
Filter merged flood events by country.

Run:
    python filter_events_by_country.py
"""

from pathlib import Path
import shutil

import rasterio
import geopandas as gpd
from shapely.geometry import box

# ------------ CONFIG -----------------

IN_DIR = Path("data/events_merged")
OUT_DIR = Path("data/events_filtered")
NE_SHAPE = Path("data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")

TARGET_COUNTRIES = ["France", "Spain", "Italy", "Portugal"]

# -------------------------------------


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Load Natural Earth countries from local file
    if not NE_SHAPE.exists():
        raise FileNotFoundError(
            f"Natural Earth shapefile not found at {NE_SHAPE}.\n"
            "Download from https://www.naturalearthdata.com/downloads/110m-cultural-vectors/"
        )

    world = gpd.read_file(NE_SHAPE).to_crs("EPSG:4326")

    # Some datasets use admin field names differently (ISO_A3, NAME, ADMIN, etc.)
    # We normalize country names.
    if "ADMIN" in world.columns:
        name_field = "ADMIN"
    elif "NAME" in world.columns:
        name_field = "NAME"
    else:
        raise ValueError("Country name column not found. Inspect the shapefile fields.")

    countries = world[world[name_field].isin(TARGET_COUNTRIES)].copy()

    if countries.empty:
        raise ValueError("No matching target countries found in shapefile.")

    # Union of all selected countries
    target_geom = countries.geometry.unary_union

    # 2) Iterate event rasters
    tifs = sorted(IN_DIR.glob("*.tif"))
    if not tifs:
        print(f"No .tif files found in {IN_DIR}")
        return

    kept, skipped = 0, 0

    for tif in tifs:
        with rasterio.open(tif) as src:
            b = src.bounds  # should already be in EPSG:4326
            event_poly = box(b.left, b.bottom, b.right, b.top)

        if event_poly.intersects(target_geom):
            shutil.copy2(tif, OUT_DIR / tif.name)
            kept += 1
            print(f"KEEP   {tif.name}")
        else:
            skipped += 1
            print(f"SKIP   {tif.name}")

    print("\nDone.")
    print(f"Kept {kept} events, skipped {skipped}.")
    print(f"Filtered events written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
