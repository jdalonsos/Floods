import glob
import os
import subprocess

def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd)

# Process all .tif in the CURRENT folder (set by the .bat with cd)
inputs = sorted(glob.glob("*.tif"))

workdir = os.getcwd()
outdir = os.path.join(workdir, "ready_plot")
os.makedirs(outdir, exist_ok=True)

print("Working folder:", workdir)
print("Output folder:", outdir)
print("Found", len(inputs), "tif files")

for f in inputs:
    base = os.path.splitext(f)[0]
    tmp = os.path.join(outdir, base + "_3857_60m_tmp.tif")
    cog = os.path.join(outdir, base + "_3857_60m_cog.tif")


    if os.path.exists(cog):
        print("SKIP (exists):", cog)
        continue

    run([
        "gdalwarp",
        "-t_srs", "EPSG:3857",
        "-tr", "60", "60",
        "-r", "max",
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
