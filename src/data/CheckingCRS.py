from pathlib import Path
import rioxarray as rxr

# 🔧 Change this to your root folder
ROOT_DIR = Path("data/floods")

tif_files = list(ROOT_DIR.rglob("*.tif"))

print(f"Found {len(tif_files)} GeoTIFF files\n")

crs_summary = {}

for tif in tif_files:
    try:
        da = rxr.open_rasterio(tif, masked=True)
        crs = da.rio.crs
        crs_str = str(crs) if crs is not None else "NO_CRS"
    except Exception as e:
        crs_str = f"ERROR: {e}"

    crs_summary.setdefault(crs_str, []).append(tif)

# 🔍 Print summary by CRS
for crs_str, files in crs_summary.items():
    print("\n" + "="*80)
    print(f"CRS: {crs_str}")
    print(f"Number of files: {len(files)}")
    for f in files[:10]:  # only show first 10 per CRS
        print("  -", f)
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")