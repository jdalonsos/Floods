import os
import shutil
from collections import defaultdict

import rasterio
from rasterio.warp import transform_bounds
import geopandas as gpd
from shapely.geometry import box

# =========================
# CONFIG
# =========================
DATA_ROOT = r"data/JRC_flood_depth_maps/"
COUNTRIES_SHP = r"data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp"

TARGET = {"France", "Belgium", "Italy", "Luxembourg"}

# =========================
# LOAD TARGET AREA (once)
# =========================
countries = gpd.read_file(COUNTRIES_SHP).to_crs("EPSG:4326")
target_poly = countries[countries["NAME"].isin(TARGET)].dissolve()
target_geom = target_poly.geometry.iloc[0]

# =========================
# EVENT PARSER
# =========================
def parse_event_id(filename: str) -> str:
    # Example:
    # WD_MERGE_2024-12-16---2024-12-23_duration_7_days_cluster_316_A0_...
    return filename.split("_cluster_")[0]
# This is saying : hey if it is the same flood event (same cluster), we consider it as the same event. to after have the fill flood event extent.
# =========================
# MAIN LOOP PER YEAR
# =========================
for year in sorted(os.listdir(DATA_ROOT)):
    year_path = os.path.join(DATA_ROOT, year)

    # skip already filtered folders or non-folders
    if not os.path.isdir(year_path):
        continue
    if year.endswith("_filtered"):
        continue

    print(f"\n Processing year {year}")

    # -------------------------
    # collect rasters by event
    # -------------------------
    event_to_files = defaultdict(list)

    for fn in os.listdir(year_path):
        if fn.lower().endswith(".tif"):
            event_id = parse_event_id(fn)
            event_to_files[event_id].append(os.path.join(year_path, fn))

    if not event_to_files:
        print("No rasters found, skipping.")
        continue

    # -------------------------
    # detect events to keep
    # -------------------------
    keep_events = set()

    for event_id, files in event_to_files.items():
        for fp in files:
            with rasterio.open(fp) as src:
                b = transform_bounds(
                    src.crs,
                    "EPSG:4326",
                    *src.bounds,
                    densify_pts=21
                )
            tile_geom = box(b[0], b[1], b[2], b[3])

            if tile_geom.intersects(target_geom):
                keep_events.add(event_id)
                break

    print(f"  ✔ Events kept: {len(keep_events)} / {len(event_to_files)}")

    # -------------------------
    # create output folder
    # -------------------------
    out_dir = os.path.join(DATA_ROOT, f"{year}_filtered")
    os.makedirs(out_dir, exist_ok=True)

    # -------------------------
    # copy kept rasters
    # -------------------------
    kept_tiles = 0
    for event_id in keep_events:
        for src_fp in event_to_files[event_id]:
            dst_fp = os.path.join(out_dir, os.path.basename(src_fp))
            if not os.path.exists(dst_fp):
                shutil.copy2(src_fp, dst_fp)
                kept_tiles += 1

    print(f"   Tiles copied: {kept_tiles}")

print("\n All years processed.")
