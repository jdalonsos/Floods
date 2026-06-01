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

For a beginner-friendly deep walkthrough of the whole dashboard display process, see [docs/streamlit_raster_dashboard_deep_guide.md](/D:/M2_MoSEF/DataCollection/docs/streamlit_raster_dashboard_deep_guide.md).

## How to Run the Main Europe Pipeline

```bash
python src/granular_tabularization.py \
  --lau data/raw/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/raw/NUTS_RG_01M_2024_4326.gpkg \
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
  --lau data/raw/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/raw/NUTS_RG_01M_2024_4326.gpkg \
  --adminexpress data/raw/adminexpress-cog-simpl-000-2025.gpkg \
  --commune-history data/raw/insee_history/v_commune_depuis_1943.csv \
  --commune-movements data/raw/insee_history/v_mvt_commune_2025.csv \
  --out-dir data/processed/france_lau_insee_documentation
```

## How to Check Point Locations Against JRC Floods

Use [src/check_points_against_jrc_floods.py](/D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods.py) when you have one or many latitude / longitude points and want to know whether they were hit by any JRC flood event.

For a deeper implementation walkthrough, see [docs/check_points_against_jrc_floods_deep_guide.md](/D:/M2_MoSEF/DataCollection/docs/check_points_against_jrc_floods_deep_guide.md).

The workflow is intentionally optimized in two stages:

- first map each point to its Eurostat LAU polygon
- use the processed JRC LAU event table to keep only candidate events touching that LAU
- open official TIFF rasters only for those candidate events
- check both the `40 m` point buffer and the `1 km` surrounding buffer around it

This is much faster than testing every point against every TIFF, especially once you scale from a few example cities to hundreds of addresses.

Default inputs:

- point workbook: `data/raw/france_20_gps_google_maps.xlsx`
- LAU polygons: `data/raw/LAU_RG_01M_2024_4326.gpkg`
- processed JRC event table: `data/processed/_outputs_eurostat_full/events_lau_long.parquet`
- France lookup enrichment: `data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv`
- raw JRC TIFF root: `data/JRC_flood_depth_maps`

Default output:

- `data/processed/france_points_jrc_flood_check.xlsx`

The output workbook contains three sheets:

- `point_summary`: original point columns plus flood flags, LAU / INSEE / NUTS metadata, candidate-event counts, and max flood indicators for both the 40 m point buffer and the 1 km surrounding buffer
- `candidate_events`: all candidate JRC events for each mapped point, including the TIFF file, event dates, and both buffer scales
- `event_hits`: only the positive hits at either buffer scale

Run it with:

```bash
python src/check_points_against_jrc_floods.py
```

Example with a study period, the default 1 km surrounding buffer, and a minimum flood threshold:

```bash
python src/check_points_against_jrc_floods.py \
  --study-start 2018-01-01 \
  --study-end 2024-12-31 \
  --buffer-km 1 \
  --threshold-cm 10 \
  --out-file data/processed/france_points_jrc_flood_check_2018_2024.xlsx
```

### T20 Portfolio Rule

For `data/processed/T20_Anonymised.xlsx`, the matching logic can be kept simple and still remain correct for this project:

1. map each `LAT` / `LONG` point to its LAU
2. keep only JRC events already touching that LAU
3. for each row, build a study window as:
   - `study_period_start = full history` by default
   - `study_period_end = Closed_Default_Date`
   - if `Closed_Default_Date` is empty, use `Cut_off_Date` instead
4. keep only JRC events whose `[start_date, end_date]` interval overlaps that row-specific study window
5. inspect the remaining TIFFs with:
   - a `40 m` point buffer for the local match metrics
   - a `1 km` surrounding buffer for the broader nearby context

That is the recommended balance here:

- simple, because the time rule is just one interval overlap per row
- fast, because the LAU prefilter avoids opening irrelevant TIFFs
- robust, because the final flood decision still comes from the raster itself rather than only from the tabular prefilter

Coordinate parsing for the T20-style workbook is handled inside:

- `load_points_table()`
- via `parse_coordinate_series()`
- with helper `normalize_decimal_text()`

That is what allows the script to accept both:

- decimal dots like `47.87431063`
- decimal commas like `47,87431063`

If you still want the old bounded lookback, you can pass `--row-study-lookback-years X`.

Example command for the new default full-history T20 logic:

```bash
python src/check_points_against_jrc_floods.py \
  --points-file data/processed/T20_Anonymised.xlsx \
  --sheet-name Feuil2 \
  --latitude-col LAT \
  --longitude-col LONG \
  --row-study-anchor-col Reference_Date \
  --row-study-end-col Closed_Default_Date \
  --row-study-end-fallback-col Cut_off_Date \
  --point-buffer-m 40 \
  --buffer-km 1 \
  --out-file data/processed/T20_Anonymised_jrc_flood_check.xlsx
```

The output workbook will also keep the raw T20 date columns and add:

- `study_period_anchor_date`
- `study_period_primary_end_date`
- `study_period_fallback_end_date`
- `study_period_start`
- `study_period_end`
- `study_period_end_source`

Interpretation of the main flags:

- `lau_matched = False`: the point did not fall inside any LAU polygon in the supplied LAU layer
- `lau_touched_by_any_jrc_event = False`: the point was mapped to a LAU, but that LAU never appears in the processed JRC flood-event table
- `jrc_flood_hit = False`: the LAU was touched by one or more JRC events, but no flooded pixel above threshold was found inside the `40 m` point buffer or the `1 km` surrounding buffer
- `jrc_flood_hit = True`: at least one JRC event produced flooded pixels above threshold inside the `40 m` point buffer or the `1 km` surrounding buffer

Important metric meaning:

- `hit_at_point_event_count` now means event hits inside the `40 m` point buffer, not only one exact raster pixel
- `hit_within_buffer_event_count` now means event hits inside the `1 km` surrounding buffer
- `hit_event_count` already counts positive matched flood events inside the main row window, meaning from the past up to `Closed_Default_Date`, or up to `Cut_off_Date` when `Closed_Default_Date` is empty
- `hit_event_count_until_default_date` is the additional feature that counts positive matched flood events from the past up to the default-start date, which in this workflow is `Reference_Date`
- `hit_event_count_until_default_date` is only a descriptive feature in `point_summary`; it does not change the main candidate filtering or the final `jrc_flood_hit` logic
- `max_point_buffer_*` columns summarize the `40 m` point-buffer depth metrics
- `max_buffer_*` columns summarize the `1 km` surrounding-buffer depth metrics

The script is designed so that later you can replace city-centre example points with large address lists converted to latitude / longitude and keep the same flood-check workflow.

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
