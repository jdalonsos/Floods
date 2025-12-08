# app.py
import numpy as np
from pathlib import Path

import streamlit as st
import rioxarray
import folium
from streamlit_folium import st_folium
import matplotlib.cm as cm

# ------------------ STREAMLIT PAGE CONFIG ------------------
st.set_page_config(page_title="Flood events dashboard", layout="wide")
st.title("🌊 Flood events dashboard")

# ------------------ DATA: LIST TIF FILES -------------------
flood_dir = Path("data/events_merged")
tif_files = sorted(flood_dir.glob("*.tif"))

if not tif_files:
    st.error("No .tif files found in data/floods/")
    st.stop()

file_labels = [f.name for f in tif_files]
selected_label = st.sidebar.selectbox("Select flood event", file_labels)
selected_file = next(f for f in tif_files if f.name == selected_label)

st.sidebar.write("Selected file:")
st.sidebar.code(str(selected_file), language="bash")

# ------------------ READ RASTER WITH RIOXARRAY -------------
# Open raster (assumed single band)
da = rioxarray.open_rasterio(selected_file)
da = da.squeeze("band", drop=True)  # remove band dimension

# If CRS is missing, set it manually (your EFAS files are in EPSG:27704)
if da.rio.crs is None:
    da = da.rio.write_crs("EPSG:27704")

# Optional: light downsampling for faster display if very large
max_size = 3000  # maximum pixels in width/height
ny, nx = da.sizes["y"], da.sizes["x"]
scale = max(ny, nx) / max_size
if scale > 1:
    factor = int(np.ceil(scale))
    da = da.coarsen(y=factor, x=factor, boundary="trim").mean()

# ------------------ REPROJECT TO WGS84 (LAT/LON) -----------
da_ll = da.rio.reproject("EPSG:4326")

# Get data as float, apply nodata mask
nodata = da_ll.rio.nodata
arr = da_ll.values.astype(float)

if nodata is not None:
    arr[arr == nodata] = np.nan

# Treat non-positive values as "no flood"
arr[arr <= 0] = np.nan

# ------------------ INTENSITY STRETCH & COLORMAP -----------
valid = arr[~np.isnan(arr)]
if valid.size == 0:
    st.warning("This raster has no valid (non-nodata) flood pixels.")
    st.stop()

# Percentile stretch to enhance contrast
vmin = float(np.nanpercentile(valid, 2))
vmax = float(np.nanpercentile(valid, 98))

# Normalise to 0–1
norm = (arr - vmin) / (vmax - vmin)
norm = np.clip(norm, 0, 1)

# Choose a multicolour intensity colormap (similar to your example)
cmap = cm.get_cmap("turbo")  # try 'jet', 'plasma', 'viridis' if you prefer
rgba = cmap(norm)            # shape (ny, nx, 4), values in [0,1]

# Alpha: 0 where no flood (nan), 1 where flooded
alpha_mask = ~np.isnan(arr)
rgba[..., 3] = np.where(alpha_mask, rgba[..., 3], 0.0)

# ------------------ BUILD EUROPE MAP WITH FOLIUM -----------
minx, miny, maxx, maxy = da_ll.rio.bounds()
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

# Opacity slider in the UI
default_opacity = 0.8
overlay_opacity = st.sidebar.slider(
    "Flood overlay opacity", 0.0, 1.0, default_opacity, 0.05
)

st.subheader("Flood intensity in European context")

# Create the base map (Leaflet)
m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
folium.TileLayer("OpenStreetMap").add_to(m)

# Add flood intensity overlay (only flood pixels visible)
image_overlay = folium.raster_layers.ImageOverlay(
    name="Flood intensity",
    image=rgba,  # RGBA array with transparency
    bounds=[[miny, minx], [maxy, maxx]],  # south-west, north-east (lat, lon)
    opacity=overlay_opacity,  # global opacity multiplier
    interactive=True,
    cross_origin=False,
)

image_overlay.add_to(m)
folium.LayerControl().add_to(m)

# Display map in Streamlit
st_folium(m, width=1000, height=700)

# ------------------ SIDEBAR: RASTER STATS ------------------
st.sidebar.markdown("### Raster info")
st.sidebar.write(f"**Original CRS:** {da.rio.crs}")
st.sidebar.write("**Display CRS:** EPSG:4326")
st.sidebar.write(f"**Bounds (lon/lat):** [{minx:.3f}, {miny:.3f}, {maxx:.3f}, {maxy:.3f}]")
st.sidebar.write(f"**Min intensity (after mask):** {valid.min():.3f}")
st.sidebar.write(f"**Max intensity (after mask):** {valid.max():.3f}")
st.sidebar.write(f"**Mean intensity:** {valid.mean():.3f}")
