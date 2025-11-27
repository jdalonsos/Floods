# app.py
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr
import streamlit as st
import rioxarray
import folium
from streamlit_folium import st_folium
import matplotlib.cm as cm

# ------------------ STREAMLIT PAGE CONFIG ------------------
st.set_page_config(page_title="Flood events dashboard", layout="wide")
st.title("🌊 Flood events dashboard")

# ------------------ DATA: LIST TIF FILES -------------------
flood_dir = Path("data/floods")
tif_files = sorted(flood_dir.glob("*.tif"))

if not tif_files:
    st.error("No .tif files found in data/floods/")
    st.stop()

# ---- Group files by event (start/end date) ----------------
# Filenames:
# WD_MERGE_[start]---[end]_duration_[...].tif
pattern = re.compile(
    r"WD_MERGE_(\d{4}-\d{2}-\d{2})---(\d{4}-\d{2}-\d{2})_duration_"
)

def event_key(path: Path) -> str:
    m = pattern.search(path.name)
    if not m:
        # fallback: use full filename if pattern not found
        return path.name
    start, end = m.groups()
    return f"{start} → {end}"

events = defaultdict(list)
for f in tif_files:
    key = event_key(f)
    events[key].append(f)

# Sidebar: choose an event (date range)
event_labels = sorted(events.keys())
selected_event = st.sidebar.selectbox(
    "Select flood event (date range)", event_labels
)

selected_files = events[selected_event]
st.sidebar.write(f"{len(selected_files)} cluster file(s) in this event:")
for f in selected_files:
    st.sidebar.caption(f"- {f.name}")

# ------------------ FUNCTION: MOSAIC CLUSTERS --------------
def load_and_mosaic(files, max_size=3000):
    """Open all GeoTIFFs in `files`, reproject to common grid,
    take max intensity across clusters, optionally downsample."""
    # 1) open all rasters as DataArrays
    das = [rioxarray.open_rasterio(str(f)).squeeze("band", drop=True)
           for f in files]

    # 2) ensure CRS is set (adapt EPSG if your files differ)
    if das[0].rio.crs is None:
        das = [da.rio.write_crs("EPSG:27704") for da in das]
    base = das[0]

    # 3) reproject each raster to match the base grid
    das_match = [da.rio.reproject_match(base) for da in das]

    # 4) stack along "cluster" dimension and take max intensity
    stack = xr.concat(das_match, dim="cluster")
    da_merged = stack.max(dim="cluster")

    # 5) optional downsampling for speed
    ny, nx = da_merged.sizes["y"], da_merged.sizes["x"]
    scale = max(ny, nx) / max_size
    if scale > 1:
        factor = int(np.ceil(scale))
        da_merged = da_merged.coarsen(
            y=factor, x=factor, boundary="trim"
        ).mean()

    return da_merged

# ------------------ READ & MERGE RASTERS -------------------
da = load_and_mosaic(selected_files, max_size=3000)

# If CRS is missing, set it manually (your EFAS files are in EPSG:27704)
if da.rio.crs is None:
    da = da.rio.write_crs("EPSG:27704")

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
    st.warning("This merged raster has no valid (non-nodata) flood pixels.")
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

st.subheader(f"Flood intensity for event: {selected_event}")

# Create the base map (Leaflet)
m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
folium.TileLayer("OpenStreetMap").add_to(m)

# Add flood intensity overlay (only flood pixels visible)
image_overlay = folium.raster_layers.ImageOverlay(
    name="Flood intensity (merged clusters)",
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
st.sidebar.markdown("### Merged raster info")
st.sidebar.write(f"**Event:** {selected_event}")
st.sidebar.write(f"**# of cluster files:** {len(selected_files)}")
st.sidebar.write(f"**Original CRS:** {da.rio.crs}")
st.sidebar.write("**Display CRS:** EPSG:4326")
st.sidebar.write(
    f"**Bounds (lon/lat):** "
    f"[{minx:.3f}, {miny:.3f}, {maxx:.3f}, {maxy:.3f}]"
)
st.sidebar.write(f"**Min intensity (after mask):** {valid.min():.3f}")
st.sidebar.write(f"**Max intensity (after mask):** {valid.max():.3f}")