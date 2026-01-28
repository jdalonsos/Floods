import glob
import os
import subprocess

def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd)

# Process all .tif in the CURRENT folder (set by the .bat with cd)
inputs = sorted(glob.glob("*.tif"))

print("Working folder:", os.getcwd())
print("Found", len(inputs), "tif files")

for f in inputs:
    base = os.path.splitext(f)[0]
    tmp = base + "_3857_60m_tmp.tif"
    cog = base + "_3857_60m_cog.tif"

    if os.path.exists(cog):
        print("SKIP (exists):", cog)
        continue

    run([
        "gdalwarp",
        "-t_srs", "EPSG:3857",
        "-tr", "60", "60",
        "-r", "bilinear",
        "-dstnodata", "9999",
        "-ot", "UInt16",
        "-multi",
        "-wo", "NUM_THREADS=ALL_CPUS",
        "-co", "TILED=YES",
        "-co", "COMPRESS=DEFLATE",
        "-co", "BIGTIFF=IF_SAFER",
        f, tmp
    ])

    run(["gdaladdo", "-r", "average", tmp, "2", "4", "8", "16", "32"])

    run([
        "gdal_translate",
        tmp, cog,
        "-of", "COG",
        "-co", "COMPRESS=DEFLATE",
        "-co", "BIGTIFF=IF_SAFER"
    ])

    # optional cleanup
    try:
        os.remove(tmp)
    except Exception as e:
        print("Warning: can't delete tmp:", tmp, e)
