import numpy as np
from pathlib import Path

import streamlit as st
import rioxarray
import folium
from streamlit_folium import st_folium
import matplotlib.cm as cm

# ------------------ STREAMLIT PAGE CONFIG ------------------
st.set_page_config(page_title="Flood events dashboard", layout="wide")
st.title(" Flood events dashboard")

# ------------------ DATA: LIST TIF FILES -------------------
flood_dir = Path("JRC_flood_depth_maps/2024")
tif_files = sorted(flood_dir.glob("*.tif"))

if not tif_files:
    st.error("No .tif files found in data/floods/")
    st.stop()

file_labels = [f.name for f in tif_files]
selected_label = st.sidebar.selectbox("Select flood event", file_labels)
selected_file = next(f for f in tif_files if f.name == selected_label)

st.sidebar.write("Selected file:")
st.sidebar.code(str(selected_file), language="bash")

# ------------------ READ RASTER (LAZY + CHUNKS) ------------
# 1. Open with chunks so it doesn't load full raster in RAM
# 2. masked=True to handle nodata cleanly
da = rioxarray.open_rasterio(
    selected_file,
    masked=True,
    chunks={"x": 2048, "y": 2048},  # <-- VERY IMPORTANT
)

# Remove band dimension
da = da.squeeze("band", drop=True)

# If CRS is missing, set it manually (EFAS uses EPSG:27704)
if da.rio.crs is None:
    da = da.rio.write_crs("EPSG:27704")

# ------------------ COMPUTE TARGET SIZE --------------------
max_size = 3000  # maximum pixels in width/height for display

ny, nx = da.sizes["y"], da.sizes["x"]
scale = max(ny, nx) / max_size

if scale > 1:
    out_height = int(ny / scale)
    out_width = int(nx / scale)
else:
    out_height = ny
    out_width = nx

# ------------------ REPROJECT + DOWNSAMPLE IN ONE STEP -----
# This uses GDAL internally to reproject straight into a small grid.
# We never materialize the HUGE original in memory.
da_ll = da.rio.reproject(
    "EPSG:4326",
    shape=(out_height, out_width),
)

# ------------------ GET ARRAY & MASK -----------------------
nodata = da_ll.rio.nodata

# .values is now only ~3000x3000 => OK for RAM
arr = da_ll.values.astype("float32")

if nodata is not None:
    arr[arr == nodata] = np.nan

# Treat non-positive values as "no flood"
arr[arr <= 0] = np.nan

# ------------------ INTENSITY STRETCH & COLORMAP -----------
valid = arr[~np.isnan(arr)]
if valid.size == 0:
    st.warning("This raster has no valid (non-nodata) flood pixels.")
    st.stop()

vmin = float(np.nanpercentile(valid, 2))
vmax = float(np.nanpercentile(valid, 98))

norm = (arr - vmin) / (vmax - vmin)
norm = np.clip(norm, 0, 1)

cmap = cm.get_cmap("turbo")
rgba = cmap(norm)  # (ny, nx, 4)

alpha_mask = ~np.isnan(arr)
rgba[..., 3] = np.where(alpha_mask, rgba[..., 3], 0.0)

# ------------------ BUILD EUROPE MAP WITH FOLIUM -----------
minx, miny, maxx, maxy = da_ll.rio.bounds()
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

default_opacity = 0.8
overlay_opacity = st.sidebar.slider(
    "Flood overlay opacity", 0.0, 1.0, default_opacity, 0.05
)

st.subheader("Flood intensity in European context")

m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
folium.TileLayer("OpenStreetMap").add_to(m)

image_overlay = folium.raster_layers.ImageOverlay(
    name="Flood intensity",
    image=rgba,
    bounds=[[miny, minx], [maxy, maxx]],
    opacity=overlay_opacity,
    interactive=True,
    cross_origin=False,
)

image_overlay.add_to(m)
folium.LayerControl().add_to(m)

st_folium(m, width=1000, height=700)

# ------------------ SIDEBAR: RASTER STATS ------------------
st.sidebar.markdown("### Raster info")
st.sidebar.write(f"**Original CRS:** {da.rio.crs}")
st.sidebar.write("**Display CRS:** EPSG:4326")
st.sidebar.write(f"**Bounds (lon/lat):** [{minx:.3f}, {miny:.3f}, {maxx:.3f}, {maxy:.3f}]")
st.sidebar.write(f"**Min intensity (after mask):** {valid.min():.3f}")
st.sidebar.write(f"**Max intensity (after mask):** {valid.max():.3f}")
st.sidebar.write(f"**Mean intensity:** {valid.mean():.3f}")
