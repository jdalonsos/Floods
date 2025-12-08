"""
Preprocess JRC flood depth maps:
- Recursively scan a root folder containing year subfolders (2015, 2016, ...).
- Group WD_MERGE GeoTIFFs by event (start/end dates in filename).
- For each event, mosaic all cluster files into one raster (max intensity).
- Optionally downsample and reproject to EPSG:4326.
- Save one output GeoTIFF per event in an output folder.

Run:
    python preprocess_events.py
"""

import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr
import rioxarray


# ---------------------- CONFIG ---------------------------------

# Root directory containing yearly folders (2015, 2016, ...)
ROOT_DIR = Path("JRC_flood_depth_maps/2024")

# Where to save merged per-event rasters
OUT_DIR = Path("data/events_merged")

# Max size (in pixels) for width/height after downsampling.
# 1000 is usually enough for dashboards, increase if you want more detail.
MAX_SIZE = 2000

# Default CRS of original WD_MERGE rasters if they lack CRS
# (Adapt this if metadata says otherwise)
DEFAULT_CRS = "EPSG:27704"

# Reproject final output to this CRS (for web maps / folium).
OUT_CRS = "EPSG:4326"

# ---------------------------------------------------------------

# Filenames follow:
# WD_MERGE_[start]---[end]_duration_[...].tif
EVENT_PATTERN = re.compile(
    r"WD_MERGE_(\d{4}-\d{2}-\d{2})---(\d{4}-\d{2}-\d{2})_duration_"
)


def find_all_tifs(root: Path):
    """Recursively find all .tif files under root."""
    return sorted(root.rglob("*.tif"))


def event_key(path: Path) -> str:
    """
    Extract (start, end) from filename.
    Returns a key like '2024-12-16__2024-12-23'.
    If pattern not found, fallback to filename stem.
    """
    m = EVENT_PATTERN.search(path.name)
    if not m:
        return path.stem
    start, end = m.groups()
    return f"{start}__{end}"


def group_files_by_event(tif_files):
    """Return dict: event_key -> [Path, Path, ...]."""
    events = defaultdict(list)
    for f in tif_files:
        key = event_key(f)
        events[key].append(f)
    return events


def load_and_mosaic(files, max_size=MAX_SIZE):
    """
    Open all GeoTIFFs in `files` safely:
    - EARLY downsampling before any large memory operations
    - force float32 to reduce RAM usage
    - reproject to common grid
    - merge using max intensity
    """
    # 1) Open rasters
    das = [
        rioxarray.open_rasterio(str(f)).squeeze("band", drop=True)
        for f in files
    ]

    # 2) Ensure CRS exists
    if das[0].rio.crs is None:
        das = [da.rio.write_crs(DEFAULT_CRS) for da in das]

    # ----------------------------
    # 🔥 3) EARLY DOWNSAMPLE
    # ----------------------------
    # Use dimensions of first raster to decide scaling
    ny, nx = das[0].sizes["y"], das[0].sizes["x"]
    scale = max(ny, nx) / max_size

    if scale > 1:
        factor = int(np.ceil(scale))
        print(f"    Downsampling by factor {factor} to avoid RAM explosion...")
        das = [
            da.coarsen(y=factor, x=factor, boundary="trim").mean()
            for da in das
        ]

    # After downsampling, choose base for reprojection
    base = das[0]

    # 4) Reproject all rasters to match base
    das_match = [da.rio.reproject_match(base) for da in das]

    # 5) Clean nodata and ensure float32
    cleaned = []
    for da in das_match:
        arr = da.values.astype("float32")  # 🔥 avoid float64
        nodata = da.rio.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan
        arr[arr <= 0] = np.nan

        da_clean = xr.DataArray(
            arr,
            coords=da.coords,
            dims=da.dims,
            attrs=da.attrs,
        )
        cleaned.append(da_clean)

    # 6) Merge using max across clusters
    stack = xr.concat(cleaned, dim="cluster")
    da_merged = stack.max(dim="cluster", skipna=True)

    # 7) Carry CRS
    da_merged = da_merged.rio.write_crs(base.rio.crs)

    return da_merged



def preprocess_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scanning GeoTIFFs under: {ROOT_DIR}")
    tif_files = find_all_tifs(ROOT_DIR)
    if not tif_files:
        print("No .tif files found. Check ROOT_DIR.")
        return

    print(f"Found {len(tif_files)} .tif files. Grouping by event...")
    events = group_files_by_event(tif_files)
    print(f"Detected {len(events)} unique events.\n")

    for i, (key, files) in enumerate(events.items(), start=1):
        start_end = key  # e.g. "2024-12-16__2024-12-23"
        out_name = f"flood_{start_end}.tif"
        out_path = OUT_DIR / out_name

        if out_path.exists():
            print(f"[{i}/{len(events)}] {start_end} → already processed, skip.")
            continue

        print(f"[{i}/{len(events)}] Processing event {start_end} "
              f"({len(files)} file(s)) ...")

        try:
            # Merge clusters
            da_merged = load_and_mosaic(files, max_size=MAX_SIZE)

            # Reproject to OUT_CRS (e.g. EPSG:4326)
            da_out = da_merged.rio.reproject(OUT_CRS)

            # Save as GeoTIFF (compressed)
            da_out.rio.to_raster(
                out_path,
                compress="LZW",
                dtype="float32",
            )
            print(f"    Saved: {out_path}")
        except Exception as e:
            print(f"    ERROR processing event {start_end}: {e}")

    print("\nDone. All merged events written to:", OUT_DIR)


if __name__ == "__main__":
    preprocess_all()
