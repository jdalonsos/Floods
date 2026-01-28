import re
from collections import defaultdict
from pathlib import Path
import xarray as xr
import rioxarray
import geopandas as gpd
from osgeo import gdal  # <--- The secret weapon for low memory merging

# ---------------------- CONFIG ---------------------------------
ROOT_DIR = Path("JRC_flood_depth_maps/2024")
OUT_DIR = Path("data/events_merged")
OUT_CRS = "EPSG:4326"

# Downsampling: 1 = Original, 2 = Half size, etc.
DOWNSAMPLE_FACTOR = 1  

LAND_SHAPEFILE = Path("data/ne_10m_land/ne_10m_land.shp")
# ---------------------------------------------------------------

EVENT_PATTERN = re.compile(
    r"WD_MERGE_(\d{4}-\d{2}-\d{2})---(\d{4}-\d{2}-\d{2})_duration_"
)

def build_vrt_mosaic(files, output_vrt_path):
    """
    Creates a Virtual Raster (VRT) file. 
    This is a 'pointer' file that merges TIFs without using RAM.
    """
    vrt_options = gdal.BuildVRTOptions(resampleAlg='nearest', addAlpha=False)
    # Convert Paths to strings for GDAL
    file_strs = [str(f) for f in files]
    
    # This runs in C++, outside of Python's memory limit
    gdal.BuildVRT(str(output_vrt_path), file_strs, options=vrt_options)
    return output_vrt_path

def process_event(key, files, out_path):
    temp_vrt = Path(f"temp_{key}.vrt")
    
    try:
        # --- STEP 1: LOAD (The RAM-Safe Way) ---
        if len(files) == 1:
            # OPTIMIZATION: If it's just 1 file, don't merge anything.
            # Just open it directly. This solves your 8.38 GiB error.
            print(f"    Single file detected. Skipping merge.")
            da = rioxarray.open_rasterio(files[0], chunks={"x": 2048, "y": 2048}).squeeze("band", drop=True)
        else:
            # If multiple files, build a VRT first.
            # This solves your 45.3 GiB error.
            print(f"    Building Virtual Mosaic (VRT) for {len(files)} tiles...")
            build_vrt_mosaic(files, temp_vrt)
            
            # Open the VRT lazily
            da = rioxarray.open_rasterio(temp_vrt, chunks={"x": 2048, "y": 2048}).squeeze("band", drop=True)

        # --- STEP 2: DOWNSAMPLE (Lazy) ---
        if DOWNSAMPLE_FACTOR > 1:
            print(f"    Downsampling by factor {DOWNSAMPLE_FACTOR}...")
            da = da.coarsen(y=DOWNSAMPLE_FACTOR, x=DOWNSAMPLE_FACTOR, boundary="trim").mean()

        # --- STEP 3: MASK (Lazy) ---
        # Note: Reprojecting BEFORE masking is sometimes safer for memory if CRSs differ greatly,
        # but here we follow your standard flow.
        if LAND_SHAPEFILE.exists():
            print("    Clipping to land mask (lazy)...")
            gdf = gpd.read_file(LAND_SHAPEFILE)
            if gdf.crs != da.rio.crs:
                gdf = gdf.to_crs(da.rio.crs)
            da = da.rio.clip(gdf.geometry, all_touched=True, drop=False)

        # --- STEP 4: REPROJECT (Lazy) ---
        if da.rio.crs != OUT_CRS:
            print(f"    Reprojecting to {OUT_CRS}...")
            da = da.rio.reproject(OUT_CRS)

        # --- STEP 5: SAVE (Windowed) ---
        # This is the ONLY time pixels are loaded into RAM, bit by bit.
        print(f"    Saving to {out_path.name}...")
        da.rio.to_raster(
            out_path,
            compress="LZW",
            tiled=True,
            windowed=True,  # Critical for Low RAM
            dtype="float32",
        )
        print("    Done.")

    finally:
        # Cleanup temporary VRT if it exists
        if temp_vrt.exists():
            temp_vrt.unlink()

def preprocess_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tif_files = sorted(ROOT_DIR.rglob("*.tif"))
    
    if not tif_files:
        print("No .tif files found.")
        return

    # Group by event
    events = defaultdict(list)
    for f in tif_files:
        m = EVENT_PATTERN.search(f.name)
        key = f"{m.group(1)}__{m.group(2)}" if m else f.stem
        events[key].append(f)

    print(f"Detected {len(events)} unique events.\n")

    for i, (key, files) in enumerate(events.items(), start=1):
        out_name = f"flood_{key}.tif"
        out_path = OUT_DIR / out_name

        if out_path.exists():
            print(f"[{i}/{len(events)}] {key} -> Exists. Skipping.")
            continue

        print(f"[{i}/{len(events)}] Processing {key} ({len(files)} files)...")
        try:
            process_event(key, files, out_path)
        except Exception as e:
            print(f"    ERROR: {e}")
            # If GDAL is missing, warn explicitly
            if "No module named 'osgeo'" in str(e):
                print("    !!! MISSING GDAL: Run 'conda install gdal' or 'pip install gdal' !!!")

if __name__ == "__main__":
    preprocess_all()