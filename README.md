# Floods Project

This repository contains a full workflow for working with the Copernicus / JRC European Satellite-Derived Flood Depth Maps:

- event-based tabularization for Europe with Eurostat `LAU + NUTS`
- France harmonization from `LAU -> current INSEE commune`
- historical `old INSEE -> current INSEE` update tables
- efficient TIFF visualization in both notebook and Streamlit dashboard form

## Current Recommended Components

- Europe pipeline: `src/granular_tabularization.py`
- France harmonization: `src/france_lau_to_insee.py`
- Single-raster notebook inspection: `src/5_Visualize_Flood_TIFF_Map.ipynb`
- Interactive raster browser: `src/app.py`
- Shared dashboard / notebook preview engine: `src/flood_preview.py`

## Very Important Visualization Note

The flood TIFFs are **not** stored in ordinary web-map coordinates.

They are stored in an **Azimuthal Equidistant projected CRS** that is equivalent in practice to `EPSG:27704` for this dataset version.

That means:

- the raster is correct in its own projected coordinate system
- but a web map usually expects `EPSG:4326` / `EPSG:3857` logic
- if you place a projected raster directly on a web map using only a latitude/longitude bounding box, the image can be visually shifted
- this is especially noticeable near coastlines, where flood cells can appear falsely "in the sea"

### What was wrong in the old dashboard logic

The original dashboard fallback overlay used a simple image box on the web map.

That is **not sufficient** for a raster whose pixels come from a projected flood grid.

So the issue was:

- **not necessarily the TIFF**
- **not necessarily the flood data**
- but the **web overlay placement logic**

### What the current dashboard logic does

The current dashboard logic now:

1. finds the flood area with a coarse raster scan
2. reads only a detailed crop of the source TIFF
3. uses three rendering strategies depending on the event size and the selected mode
4. keeps polygon-based rendering available for alignment-sensitive inspection
5. uses raster overlay only as a fast approximate view

Those rendering strategies are:

- exact native source pixels for sparse events
- preview-grid polygon pixels for medium-size events
- raster overlay for broad qualitative previews

Important clarification:

- reprojecting the crop before overlay is necessary
- but it is **not always sufficient** to make a rectangular image overlay line up perfectly with external viewers such as Felt
- polygon-based rendering is still the more trustworthy option when spatial alignment matters

So the issue was never simply "the TIFF is wrong".

The main difference is how the web app draws the flood cells.

## Why this matters for data scientists

If you are not used to geospatial data, the important idea is:

- a TIFF can be perfectly valid
- but still look wrong on a web map
- if the application displays it without the right reprojection step

So in this project, we separate:

- **scientific raster storage CRS**
- **analysis CRS handling**
- **web visualization CRS**

That separation is necessary for both correct analytics and correct map display.

## How to Run the Dashboard

From the project root:

```bash
streamlit run src/app.py
```

If `streamlit` is not recognized:

```bash
python -m streamlit run src/app.py
```

The dashboard lets you:

- browse official TIFF rasters by year
- filter filenames
- inspect one raster quickly without loading the whole file at full resolution
- switch between `auto`, `Polygon pixels`, and `Raster overlay` rendering modes

Recommended interpretation of those modes:

- `Polygon pixels` is the most spatially faithful mode
- `Raster overlay` is the fastest mode, but also the most approximate
- `Auto` is the best default for routine browsing

## How to Run the Main Europe Pipeline

```bash
python src/granular_tabularization.py \
  --lau data/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/NUTS_RG_01M_2024_4326.gpkg \
  --flood-dir data/JRC_flood_depth_maps \
  --out-dir data/processed/_outputs_eurostat_full
```

The tabularization now also writes NUTS3 coverage diagnostics so you can check
which official NUTS3 regions exist in the Eurostat lookup versus which ones
actually appear in flood-event outputs:

- `nuts3_event_coverage.csv`
- `country_nuts3_event_coverage.csv`
- `nuts3_without_flood_events.csv`

## How to Run the France Harmonization

This command reads the canonical Europe output `events_lau_long.csv` and
creates the France-specific commune table `events_fr_insee_long.csv`.

Important implementation note:

- the Europe table already contains `nuts0` to `nuts3`
- the France lookup adds another `nuts3` mapping for documentation and fallback
- the script now resolves that merge safely, keeping the event-table `nuts3_*`
  columns as canonical and only using lookup values when the event table is
  missing them

```bash
python src/france_lau_to_insee.py \
  --tabular-file data/processed/_outputs_eurostat_full/events_lau_long.csv \
  --lau data/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/NUTS_RG_01M_2024_4326.gpkg \
  --adminexpress data/adminexpress-cog-simpl-000-2025.gpkg \
  --commune-history data/insee_history/v_commune_depuis_1943.csv \
  --commune-movements data/insee_history/v_mvt_commune_2025.csv \
  --out-dir data/processed/france_lau_insee_documentation
```

## TIFFs and Git

Flood TIFFs should **not** be pushed to GitHub from this project workflow.

The repository is configured to ignore:

- `*.tif`
- large tabular exports such as `*.parquet`, `*.xlsx`, `*.csv`

That keeps the code repository light and prevents accidental pushes of heavy raster data.

## How to Compare France JRC vs Gaspar

Use the France commune-event output from `src/france_lau_to_insee.py` together
with the cleaned first sheet of `data/processed/Gaspar_2015_2024.xlsx`.

The comparison script:

- normalizes INSEE commune codes on both sources
- uses a flexible date rule on both start and end dates
- matches on:
  - same commune code
  - `abs(jrc_start - gaspar_start) <= 7 days`
  - `abs(jrc_end - gaspar_end) <= 7 days`
- defines the Gaspar event grain as:
  - `cod_nat_catnat + dat_deb + dat_fin`
  - because one `cod_nat_catnat` can contain multiple date pairs
- writes a small top-level result pack:
  - `comparison_guide.md`
  - `comparison_summary.csv`
  - `comparison_summary.xlsx`
  - `coverage_overview.csv`
  - `coverage_overview.xlsx`
  - `best_match_overview_commune.csv`
  - `best_match_overview_commune.xlsx`
- keeps the long audit tables inside `details/`

```bash
python src/compare_france_jrc_gaspar.py \
  --jrc-file data/processed/france_lau_insee_documentation/events_fr_insee_long.csv \
  --gaspar-file data/processed/Gaspar_2015_2024.xlsx \
  --sheet-name Gaspar20152024FloodsClean \
  --date-window-days 7 \
  --out-dir data/processed/jrc_gaspar_comparison_7d
```

---

# 1. Scrapping.py

This script automatically **scrapes and downloads satellite-derived flood depth maps (`.tif`) from the JRC CEMS-EFAS server** and stores them locally by year.

## Inputs
BASE_URL = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/European_Satellite-Derived_Flood_Depth_Maps/maps/"

This is the online folder that contains subfolders like 2015/, 2016/, … 2024/

Years to download

YEARS = list(range(2015, 2025))

OUTPUT_DIR = "JRC_flood_depth_maps"


## Output 

It creates all folders by year of floods

JRC_flood_depth_maps/
├── 2015/
│   ├── *.tif
├── 2016/
│   ├── *.tif
...
└── 2024/
    ├── *.tif

Each .tif is a raster map of flood depth, usable in QGIS, ArcGIS, or Python (rasterio).

---

# 2. FilteringCountries.py


This script filters JRC flood depth rasters by country and by flood event. It keeps only events that intersect France, Belgium, Italy, or Luxembourg. If at least one tile of an event touches these countries, all tiles of that event are preserved.

## Inputs

- Path: data/JRC_flood_depth_maps/

Expected structure:
data/JRC_flood_depth_maps/
  2015/
  2016/
  ...
  2024/

Each year folder contains multiple .tif flood depth rasters.

- Country shapefile

Path: data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp.
This Natural Earth file provides national boundaries used to define the target area.


- Target countries [List]

France, Belgium, Italy, Luxembourg


## PROCESSING LOGIC


Step 1 – Build target geometry
- Load the country shapefile with GeoPandas.
- Reproject to EPSG:4326 (WGS84).
- Select the four target countries.
- Dissolve them into one single polygon (target_geom).

Step 2 – Group rasters by flood event
Each filename is parsed using the pattern before \"_cluster_\".
All rasters sharing the same cluster are treated as one flood event.

Step 3 – Detect events to keep
For each raster tile:
- Read its bounding box with rasterio.
- Reproject bounds to EPSG:4326.
- Convert bounds to a polygon.
- Test spatial intersection with target_geom.

If any tile of an event intersects the target area, the whole event is kept.



## Output


For each year YYYY, the script creates:
data/JRC_flood_depth_maps/YYYY_filtered/

Inside, it copies all rasters belonging to the kept events, for example:
2018_filtered/
  WD_MERGE_2018-10-01_..._cluster_245_A0.tif
  WD_MERGE_2018-10-01_..._cluster_245_A1.tif
  WD_MERGE_2018-10-01_..._cluster_245_A2.tif

Even tiles outside the four countries are included if they belong to a kept event.

---

# 3. Tabularization.py


Input
IGN ADMIN EXPRESS COG (commune boundaries + INSEE codes) file -> Admin Express COG simplifiée
https://www.data.gouv.fr/datasets/admin-express-cog-simplifiee-metropole-drom-saint-martin-saint-barthelemy?utm_source=chatgpt.com




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

## 7. Why a 3-step workflow?

A correct COG must contain: 1. data 2. zoom levels 3. correct internal
ordering

Therefore: - overviews must be created **before** final COG creation

------------------------------------------------------------------------

#  FINAL WORKFLOW

## Step 1 --- Warp to temporary GeoTIFF (NOT COG)

``` bat
for %f in (*.tif) do gdalwarp -t_srs EPSG:3857 ^
  -tr 60 60 -r bilinear -dstnodata 9999 -ot UInt16 ^
  -multi -wo NUM_THREADS=ALL_CPUS ^
  -co TILED=YES -co COMPRESS=DEFLATE -co BIGTIFF=IF_SAFER ^
  "%f" "%~nf_3857_60m_tmp.tif"
```

This step: - converts to web-map coordinates - reduces resolution for
speed - preserves flood depth values - creates temporary files

------------------------------------------------------------------------

## Step 2 --- Build overviews (zoom levels)

``` bat
for %f in (*_3857_60m_tmp.tif) do gdaladdo -r average "%f" 2 4 8 16 32
```

Overviews are smaller internal copies used when zooming out.

------------------------------------------------------------------------

## Step 3 --- Convert to final COG

``` bat
for %f in (*_3857_60m_tmp.tif) do gdal_translate "%f" "%~nf_cog.tif" ^
  -of COG -co COMPRESS=DEFLATE -co BIGTIFF=IF_SAFER
```

This produces the final, web-ready files.

------------------------------------------------------------------------

## 8. Result

✔ Small file size\
✔ Fast pan & zoom\
✔ Smooth dashboards\
✔ Original data preserved

------------------------------------------------------------------------

## 9. Final takeaway

> We keep the scientific data intact and create a fast, optimized
> version for interactive web maps.
> 

-------------------------------------------------------------------------------

# FAQ

## What is EPSG:4326? Why?
- A coordinate system that uses **latitude / longitude** (like **GPS**).
- Units are **degrees**, not meters.

## Why people often convert to EPSG:4326
### 1) Universal / interoperable
- Many tools, datasets, APIs, and “location” formats assume **lat/long**.
- It reduces CRS mismatch issues when you combine many sources.

### 2) Easy to share
- Like exporting to **PDF**: most people can open/use it without special setup.

### 3) Web mapping friendliness
- Many online mapping workflows handle WGS84 lat/long smoothly.

## The big downside (important)
- **Degrees ≠ meters**
- In EPSG:4326, distances/areas are not measured in meters and vary by latitude.
- So calculations like:
  - **area (km²)**
  - **distance**
  - **buffers**
  - **spatial statistics that assume constant scale**
  can be **wrong or inconsistent** in EPSG:4326.
