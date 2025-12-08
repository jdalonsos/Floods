"""
Merge all per-event flood rasters into ONE global raster (max intensity),
using the union of extents (so no events are lost outside the first raster).

Assumes:
- data/events_filtered/ contains 1 GeoTIFF per event,
  already reprojected to EPSG:4326 (or a single consistent CRS).

This script:
- Scans data/events_filtered for .tif
- Computes the UNION of all raster bounds
- Builds a global grid with that extent + resolution
- Reprojects each event raster to that global grid
- Merges via pixel-wise max, ignoring NaNs / non-positive values
- Saves ONE GeoTIFF: flood_ALL_events.tif

Run:
    python src/data/mergeAllFolder.py
"""

from pathlib import Path

import numpy as np
import xarray as xr
import rioxarray
import rasterio
from rasterio.transform import from_bounds

# ---------------------- CONFIG ---------------------------------

# Folder where your per-event rasters are stored
EVENTS_DIR = Path("data/events_filtered")

# Output path for the global raster
OUT_PATH = EVENTS_DIR / "flood_ALL_events.tif"

# Target CRS for final output (same as used in your app)
TARGET_CRS = "EPSG:4326"

# Limit size of global raster for memory (max width/height in pixels)
MAX_SIZE_GLOBAL = 2000  # tweak if needed (bigger = more detail & RAM)

# ---------------------------------------------------------------


def find_all_tifs(root: Path):
    """Return sorted list of all .tif files under root."""
    return sorted(root.glob("*.tif"))


def scan_global_extent(files):
    """
    Compute the union of bounds (in TARGET_CRS) and a representative resolution.

    We assume all rasters are already in TARGET_CRS (from your preprocess script).
    If not, you can reproject here, but that would be weird given your pipeline.
    """
    global_minx = np.inf
    global_miny = np.inf
    global_maxx = -np.inf
    global_maxy = -np.inf
    res_x = None
    res_y = None

    for i, f in enumerate(files):
        da = rioxarray.open_rasterio(str(f)).squeeze("band", drop=True)

        if da.rio.crs is None:
            raise ValueError(f"Raster {f} has no CRS; please fix preprocessing.")

        crs_str = da.rio.crs.to_string()
        if crs_str != TARGET_CRS:
            raise ValueError(
                f"Raster {f} has CRS {crs_str}, not {TARGET_CRS}. "
                "All per-event rasters should have the same CRS."
            )

        minx, miny, maxx, maxy = da.rio.bounds()

        global_minx = min(global_minx, minx)
        global_miny = min(global_miny, miny)
        global_maxx = max(global_maxx, maxx)
        global_maxy = max(global_maxy, maxy)

        if i == 0:
            # Derive pixel size from first file
            transform = da.rio.transform()
            # transform.a = pixel width (positive)
            # transform.e = pixel height (negative)
            res_x = transform.a
            res_y = -transform.e  # store as positive

    if not np.isfinite(global_minx):
        raise ValueError("Failed to compute valid global extent.")

    return global_minx, global_miny, global_maxx, global_maxy, res_x, res_y


def build_global_grid(minx, miny, maxx, maxy, res_x, res_y, max_size=MAX_SIZE_GLOBAL):
    """Create transform + shape for a global grid covering the union of extents."""

    width = int(np.ceil((maxx - minx) / res_x))
    height = int(np.ceil((maxy - miny) / res_y))

    # Optional downsampling of the global grid to keep RAM reasonable
    scale = max(width, height) / max_size
    if scale > 1:
        factor = int(np.ceil(scale))
        width = int(np.ceil(width / factor))
        height = int(np.ceil(height / factor))
        res_x = res_x * factor
        res_y = res_y * factor
        print(
            f"  Global grid downsampled by factor {factor} "
            f"to {width} x {height} pixels."
        )
    else:
        print("  No global downsampling needed.")

    # from_bounds: (west, south, east, north, width, height)
    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    return transform, width, height


def merge_event_rasters_union(files):
    """
    Merge many per-event rasters on a global grid that covers the union of extents.
    """
    print("Computing global extent and resolution from all files...")
    minx, miny, maxx, maxy, res_x, res_y = scan_global_extent(files)
    print(f"  Global bounds: [{minx:.4f}, {miny:.4f}, {maxx:.4f}, {maxy:.4f}]")
    print(f"  Base resolution: dx={res_x}, dy={res_y}")

    print("Building global grid...")
    transform, width, height = build_global_grid(
        minx, miny, maxx, maxy, res_x, res_y, max_size=MAX_SIZE_GLOBAL
    )
    print(f"  Global grid: width={width}, height={height}")

    # Prepare an empty composite array (float32, filled with NaN)
    comp_arr = np.full((height, width), np.nan, dtype="float32")

    # For each raster: reproject to this global grid, then update comp_arr = max
    for f in files:
        print(f"  Merging {f.name} ...")
        da = rioxarray.open_rasterio(str(f)).squeeze("band", drop=True)

        if da.rio.crs is None:
            raise ValueError(f"Raster {f} has no CRS; please fix preprocessing.")
        if da.rio.crs.to_string() != TARGET_CRS:
            raise ValueError(
                f"Raster {f} has CRS {da.rio.crs.to_string()}, not {TARGET_CRS}."
            )

        # Reproject directly onto the global grid
        da_warped = da.rio.reproject(
            TARGET_CRS,
            transform=transform,
            shape=(height, width),
            resampling=rasterio.enums.Resampling.nearest,
        )

        arr = da_warped.values.astype("float32")
        nodata = da_warped.rio.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan
        arr[arr <= 0] = np.nan  # treat non-positive as no flood

        mask_new = ~np.isnan(arr)
        mask_old = ~np.isnan(comp_arr)

        # Where only new has data
        comp_arr[mask_new & ~mask_old] = arr[mask_new & ~mask_old]

        # Where both have data → max
        both = mask_new & mask_old
        comp_arr[both] = np.maximum(comp_arr[both], arr[both])

    # Build xarray DataArray with correct coordinates & transform
    # y: from top (north) downward
    # x: from west to east
    ys = np.linspace(
        transform.f + transform.e / 2,
        transform.f + transform.e / 2 + (height - 1) * transform.e,
        height,
    )
    xs = np.linspace(
        transform.c + transform.a / 2,
        transform.c + transform.a / 2 + (width - 1) * transform.a,
        width,
    )

    composite = xr.DataArray(
        comp_arr,
        coords={"y": ys, "x": xs},
        dims=("y", "x"),
    )
    composite = composite.rio.write_crs(TARGET_CRS)
    composite = composite.rio.write_transform(transform)

    return composite


def main():
    print(f"Scanning event rasters in: {EVENTS_DIR}")
    tif_files = find_all_tifs(EVENTS_DIR)

    # Exclude the output file itself if it exists
    tif_files = [f for f in tif_files if f.name != OUT_PATH.name]

    if not tif_files:
        print("No per-event .tif files found. Check EVENTS_DIR.")
        return

    print(f"Found {len(tif_files)} per-event GeoTIFFs.")

    if OUT_PATH.exists():
        print(f"Output already exists: {OUT_PATH}")
        print("Delete it or rename OUT_PATH if you want to recompute.")
        return

    try:
        da_merged = merge_event_rasters_union(tif_files)

        print(f"Saving global merged raster to: {OUT_PATH}")
        da_merged.rio.to_raster(
            OUT_PATH,
            compress="LZW",
            dtype="float32",
        )
        print("Done.")
    except Exception as e:
        print(f"ERROR merging event rasters: {e}")


if __name__ == "__main__":
    main()
