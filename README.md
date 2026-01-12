# DataCollection

Streamlit app for flood events dashboard.

This project is deployed with Poetry and Streamlit.


#  Making Large Flood Maps Fast and Usable on Web Maps  
### A Beginner-Friendly Guide (No GIS Knowledge Required)

This document explains **how and why** we transform large flood map files into **fast, lightweight maps** that can be displayed smoothly in web applications (Leafmap, Streamlit, dashboards).

The explanation is written for a **general technical audience**, with **no prior knowledge of GIS or cartography**.

---

## 1. The problem we are solving (in simple words)

We start with **scientific flood maps** provided by Copernicus (JRC):

- They cover **huge geographic areas**
- They have **very fine detail** (20 meters per pixel)
- They are stored in a **scientific coordinate system**
- They are **not designed for interactive maps**

When we try to display them directly:
- Maps are slow
- Zooming freezes
- Files become extremely large
- Computers run out of memory

 **Goal:**  
Create a **display-optimized copy** of the data that is:
- fast to load
- smooth to zoom
- small in size
- visually accurate
- safe (original data stays unchanged)

---

## 2. What is GDAL?

**GDAL** stands for:

> **Geospatial Data Abstraction Library**

Think of GDAL as **the Swiss army knife for map files**.

It can:
- read map images (GeoTIFF, etc.)
- convert coordinate systems
- change resolution
- compress files
- build zoom levels
- optimize files for the web

### Why we use GDAL
- It is the **industry standard**
- Used by **QGIS, Google Earth, Copernicus, NASA**
- Extremely reliable and fast
- Works from the command line (perfect for automation)

---

## 3. What is OSGeo4W Shell (Windows)?

On Windows, GDAL needs a **special environment** to work correctly.

**OSGeo4W Shell** is:
- a terminal provided by QGIS
- pre-configured with GDAL
- guaranteed to work without errors

Without it:
- commands may not be found
- projections may fail
- results may be inconsistent

 **All commands below must be run in OSGeo4W Shell**

---

## 4. What is a coordinate system (very briefly)?

Maps are drawn using **mathematical coordinate systems**.

### Two important ones here:

| Name | Used for | Why |
|----|----|----|
| EPSG:27704 | Scientific analysis | Accurate distances |
| EPSG:3857 | Web maps (Google, OpenStreetMap) | Fast display |

Web maps **only work natively in EPSG:3857**.

 That’s why we must convert.

---

## 5. What is a GeoTIFF?

A **GeoTIFF** is:
- an image file (`.tif`)
- with geographic information embedded inside
- each pixel corresponds to a real location on Earth

It’s like a photo, **but every pixel knows where it is**.

---

## 6. What is a Cloud Optimized GeoTIFF (COG)?

A **COG** is a special type of GeoTIFF that is:

-  **Tiled** (stored in small blocks instead of long rows)
-  **Compressed** (smaller size)
-  **Multi-resolution** (contains zoom levels inside)
-  **Fast to read partially**

### Why COGs are fast
When you zoom on a map:
- only the visible tiles are read
- only the needed resolution is used
- the rest of the file is ignored

This is how Google Maps works.

---

## 7. Why we use 3 steps instead of 1

A **proper COG** must have a very specific internal structure.

If we:
- create a COG first
- then add zoom levels later

 the file becomes **sub-optimal**.

### Correct professional workflow:
1. Prepare the data
2. Build zoom levels
3. Package everything as a COG

---

#  THE COMPLETE WORKFLOW (EXPLAINED LINE BY LINE)

---

## STEP 1 — Convert to a temporary display-friendly GeoTIFF

```bat
for %f in (*.tif) do gdalwarp -t_srs EPSG:3857 ^
  -tr 60 60 -r bilinear -dstnodata 9999 -ot UInt16 ^
  -multi -wo NUM_THREADS=ALL_CPUS ^
  -co TILED=YES -co COMPRESS=DEFLATE -co BIGTIFF=IF_SAFER ^
  "%f" "%~nf_3857_60m_tmp.tif"

