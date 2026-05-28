# Geodata Pipeline Guide

This document explains the geospatial logic of the flood tabularization workflow in plain language.

It is written for a data scientist who is comfortable with Python, tables, and notebooks, but who does not already have a geospatial background.

The guide covers:

1. What the data is.
2. What the main scripts do.
3. Why specific design choices were made.
4. How to run the workflow.
5. How to interpret the outputs.
6. How the France-specific mapping works.
7. How to visualize a TIFF efficiently.
8. How the dashboard uses the same visualization logic.

## 1. Big Picture

The project starts from a satellite-derived flood depth dataset.

Each official TIFF file is one flood event map. The raster stores water depth in centimeters on a 20 m grid.

The main analytical goal is to transform those raster flood maps into tabular outputs:

- which local administrative units were affected
- how many units were affected
- what the maximum flood depth was inside each unit
- how the results aggregate to NUTS levels

For France, a second goal is to connect the European LAU codes to current INSEE commune codes, and also to map old commune codes to current ones for comparison with national datasets such as Gaspar.

## 2. Core Concepts

### Raster

A raster is a grid of cells.

Here:

- one cell is 20 m x 20 m
- each cell contains flood depth in cm
- `0` or `nodata` means background / non-flood area
- `9999` means permanent or seasonal water and should not be treated as flood depth

### Vector polygons

Administrative boundaries are polygons.

Examples:

- LAU = local administrative units
- NUTS0 = country
- NUTS1, NUTS2, NUTS3 = larger territorial aggregation levels used in European statistics

### Overlay

The central spatial operation is:

"For a given flood raster, which administrative polygons intersect the flooded pixels?"

This is the basis of the tabularization.

### CRS

CRS means coordinate reference system.

The flood TIFFs are not stored in regular latitude/longitude.

They use an Azimuthal Equidistant projected CRS that is equivalent in practice to `EPSG:27704` for this dataset version.

This matters because:

- you cannot safely compare geometries unless they are in compatible CRS
- if you treat projected raster coordinates as if they were lat/lon, the map will be wrong

The pipeline always respects the raster CRS when doing spatial analysis, and only converts to `EPSG:4326` when a web map display is needed.

## 3. Main Files

### Europe-wide tabularization

- `src/granular_tabularization.py`

Purpose:

- discovers official flood event TIFFs
- loads Eurostat LAU and NUTS
- maps each flood event to affected LAUs
- enriches each LAU with NUTS0/1/2/3
- writes canonical and aggregated outputs

### France post-processing

- `src/france_lau_to_insee.py`

Purpose:

- filters the Europe LAU output to France
- maps France LAU rows to current AdminExpress / INSEE commune codes
- creates a historical old INSEE -> current INSEE update table

### TIFF visualization notebook

- `src/5_Visualize_Flood_TIFF_Map.ipynb`

Purpose:

- quickly inspect one heavy TIFF without loading the full raster at full resolution
- provide both a static preview and an interactive map

### Shared visualization engine

- `src/flood_preview.py`

Purpose:

- hold the efficient TIFF preview logic in reusable Python code
- keep the notebook and the dashboard aligned
- avoid maintaining two different geospatial rendering methods

### Streamlit dashboard

- `src/app.py`

Purpose:

- browse official flood rasters by year
- filter filenames quickly
- preview the selected raster without editing notebook cells

## 4. Data Sources Used

### Flood rasters

Recommended source:

- `data/JRC_flood_depth_maps/`

This is the clean raw archive with year folders `2015` to `2024`.

Alternative source:

- `data/Filtered/`

This can also be used, but it contains derivative display files in some subfolders. The script is designed to reject those automatically.

### Administrative layers

Eurostat LAU:

- `data/LAU_RG_01M_2024_4326.gpkg`

Eurostat NUTS:

- `data/NUTS_RG_01M_2024_4326.gpkg`

France AdminExpress:

- `data/adminexpress-cog-simpl-000-2025.gpkg`

INSEE historical commune tables:

- `data/insee_history/v_commune_depuis_1943.csv`
- `data/insee_history/v_mvt_commune_2025.csv`

## 5. Design Choices and Why They Were Made

### Choice 1. One official TIFF file = one event

Why:

The official filename convention already encodes one flood event.

The README defines one file name pattern per event:

`WD_MERGE_[start]---[end]_duration_[days]_cluster_[flood ID]_A0_[...]_A_[...]_lat_[...]_lon_[...]_size_[...].tif`

So the correct event logic is:

- one official file = one event
- different official files = different events

This is more robust than grouping files together with a weaker key.

### Choice 2. Accept only strict official filenames

Why:

The local filtered tree contains display derivatives such as:

- `*_3857_60m_cog.tif`

Those are not new flood events. They are web-display products derived from official rasters.

If they are mixed with true event rasters, the analysis can double count or distort event logic.

So the pipeline uses a strict filename regex and rejects non-official TIFFs automatically.

### Choice 3. Use one administrative source family across Europe

Why:

Mixing a France-specific administrative source with a Europe-wide source can make cross-country logic inconsistent.

So the Europe pipeline uses:

- Eurostat LAU
- Eurostat NUTS

This creates one coherent base across all countries in the file.

### Choice 4. Use LAU as the canonical output

Why:

LAU is the most detailed common administrative level in the European source.

If the LAU table is correct, NUTS0/1/2/3 outputs can be created deterministically by aggregation.

That is why:

- `events_lau_long.csv` is the canonical table
- `events_nuts0.csv`, `events_nuts1.csv`, `events_nuts2.csv`, `events_nuts3.csv` are rollups

### Choice 5. Default `all_touched = False`

Why:

When rasterizing polygons, `all_touched=True` counts every cell touched by the polygon boundary.

That can inflate counts near boundaries.

Using `all_touched=False` is more conservative and generally more defensible for impact tabularization.

Important clarification:

- this is whole-pixel logic, not fractional area weighting
- the workflow does not assign `10%` of a pixel to a polygon just because `10%` of the pixel overlaps the boundary
- in practice, for polygon masking, `all_touched=False` behaves like a center-based rule:
  a pixel is typically counted only if its center falls inside the polygon
- `all_touched=True` is broader:
  a pixel can be counted even if the polygon only touches a small part of that pixel

Example with the default `20 m` JRC pixels:

- if Commune A overlaps only a small corner of a flood pixel, for example roughly `2 m` along the edge, that pixel will usually **not** be counted for Commune A when `all_touched=False`
- the same pixel **would** be counted for Commune A when `all_touched=True`

This matters mainly for communes that sit along flood boundaries or administrative borders.

### Choice 6. Count flooded pixels only where depth > threshold

Why:

The raster contains many non-flood or masked cells.

The logic used is:

- ignore `nodata`
- ignore `9999`
- keep only cells with `depth > threshold_cm`

This avoids counting water masks or dry cells as floods.

### Choice 7. Use a spatial index before per-polygon masking

Why:

Europe has many LAUs.

Checking every LAU against every raster would be too slow.

So the code first selects only LAUs whose bounding boxes intersect the raster footprint. Only those candidates are evaluated in detail.

This makes the Europe-scale run feasible.

### Choice 8. Use representative points for LAU -> NUTS joins

Why:

Polygon-on-polygon joins can fail on tiny geometry edge cases.

Using a representative point inside the LAU polygon is a robust way to identify the containing NUTS polygon.

The join logic is:

- try `within`
- if needed, fallback to `intersects`
- if NUTS0 is still missing, fallback to country code

### Choice 9. Separate Europe logic from France-specific harmonization

Why:

France requires an additional mapping step to current and historical INSEE commune codes.

That is a national harmonization task, not a Europe-wide administrative layer task.

So it is handled as a second script after the Europe pipeline.

## 6. How the Europe Pipeline Works

### Step 1. Load LAU and NUTS

The script reads:

- `data/LAU_RG_01M_2024_4326.gpkg`
- `data/NUTS_RG_01M_2024_4326.gpkg`

It normalizes column names and enriches every LAU with:

- `nuts0_code`, `nuts0_name`
- `nuts1_code`, `nuts1_name`
- `nuts2_code`, `nuts2_name`
- `nuts3_code`, `nuts3_name`

### Step 2. Discover official flood events

The script scans the flood directory and keeps only files that match the official README naming pattern exactly.

This avoids accidental inclusion of display derivatives.

### Step 3. Process one event at a time

For each TIFF:

1. Validate the raster properties.
2. Reproject the LAU layer to the raster CRS.
3. Use the spatial index to find candidate LAUs.
4. For each candidate LAU, mask the raster cells inside the polygon.
5. Keep only valid flooded cells.
6. Compute:
   - maximum depth in cm
   - flooded pixel count
   - flooded area in square meters

### Step 4. Write outputs

The script writes:

- `events_lau_long.csv`
- `events_summary.csv`
- `lau_nuts_lookup.csv`
- `events_nuts0.csv`
- `events_nuts1.csv`
- `events_nuts2.csv`
- `events_nuts3.csv`
- `nuts3_event_coverage.csv`
- `country_nuts3_event_coverage.csv`
- `nuts3_without_flood_events.csv`
- `flood_event_tables.xlsx`
- `run_metadata.json`

In the current workspace, the main full output folder is:

- `data/processed/_outputs_eurostat_full/`

## 7. How to Run the Europe Pipeline

### From Git Bash

From the project root:

```bash
cd "/d/M2_MoSEF/DataCollection"

python src/granular_tabularization.py \
  --lau data/raw/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/raw/NUTS_RG_01M_2024_4326.gpkg \
  --flood-dir data/JRC_flood_depth_maps \
  --out-dir data/processed/_outputs_eurostat_full
```

### From PowerShell

```powershell
Set-Location D:\M2_MoSEF\DataCollection

python src\granular_tabularization.py `
  --lau data\raw\LAU_RG_01M_2024_4326.gpkg `
  --nuts data\raw\NUTS_RG_01M_2024_4326.gpkg `
  --flood-dir data\JRC_flood_depth_maps `
  --out-dir data\processed\_outputs_eurostat_full
```

### Useful options

France only:

```bash
--countries FR
```

Specific years:

```bash
--year-from 2019 --year-to 2024
```

Small test:

```bash
--max-files 1
```

## 8. How to Interpret the Main Outputs

### `events_lau_long.csv`

One row = one `event x LAU`.

Important columns:

- event metadata
- `lau_code`, `lau_name`
- `nuts0_code` to `nuts3_name`
- `max_depth_cm`
- `flooded_pixels`
- `flooded_area_m2`

This is the most important output.

### `events_summary.csv`

One row = one event.

Useful columns:

- `n_candidate_lau`
- `n_lau_flooded`
- `n_nuts0_flooded`
- `n_nuts1_flooded`
- `n_nuts2_flooded`
- `n_nuts3_flooded`

Meaning:

- `n_candidate_lau` = how many LAUs intersect the raster footprint
- `n_lau_flooded` = how many of those actually contain flooded pixels after masking

Important interpretation:

- `n_candidate_lau = 0` does not mean the script failed
- it means the event raster lies outside the administrative coverage of the loaded LAU file

This happens because the flood archive covers "Europe and surroundings", while the LAU file covers only the countries included in the Eurostat source.

### `lau_nuts_lookup.csv`

One row per LAU with its NUTS hierarchy.

This is useful for documentation and sanity checks.

### `nuts3_event_coverage.csv`

One row per official NUTS3 region present in the Eurostat lookup.

Useful columns:

- `lookup_lau_count`
- `n_event_ids_hit`
- `has_flood_events`

This is the easiest way to check whether a region such as Corsica, Madeira,
the Azores, the Canary Islands, or the French overseas NUTS3 codes exists in
the official geography but simply does not appear in the current flood-event
outputs.

### `country_nuts3_event_coverage.csv`

One row per country summarizing:

- how many NUTS3 regions exist in the lookup
- how many were hit by at least one event
- how many were not hit

### `nuts3_without_flood_events.csv`

This is the direct audit table for NUTS3 regions that exist in the lookup but
do not appear in the current flood-event outputs.

## 9. Countries Included in the LAU File

The current LAU source contains `97,987` LAUs across `34` countries.

These countries are:

- Albania
- Austria
- Belgium
- Bulgaria
- Switzerland
- Cyprus
- Czechia
- Germany
- Denmark
- Estonia
- Greece
- Spain
- Finland
- France
- Croatia
- Hungary
- Ireland
- Iceland
- Italy
- Liechtenstein
- Lithuania
- Luxembourg
- Latvia
- North Macedonia
- Malta
- Netherlands
- Norway
- Poland
- Portugal
- Romania
- Serbia
- Sweden
- Slovenia
- Slovakia

Some surrounding-country flood events can therefore exist in the raster archive without matching any LAU polygons.

## 10. France-Specific Harmonization

### Current France LAU -> current INSEE commune

Script:

- `src/france_lau_to_insee.py`

Logic:

1. Start from the Europe LAU output.
2. Keep only France rows.
3. Match France LAU to current AdminExpress commune codes.

Matching strategy:

- first by exact code
- if exact code fails, by spatial fallback

Spatial fallback means:

- take the France LAU polygon
- compute a representative point
- find which AdminExpress commune polygon contains it

This resolves code changes between Eurostat LAU 2024 and AdminExpress 2025.

### Historical old INSEE -> current INSEE

This is also built by `src/france_lau_to_insee.py`.

It uses:

- `v_commune_depuis_1943.csv`
- `v_mvt_commune_2025.csv`

Logic:

1. Take an inactive old commune state.
2. Follow the official commune movement graph.
3. Find which current commune or communes it maps to.
4. Flag whether the mapping is:
   - unique
   - multiple
   - unresolved

This is useful when old national datasets contain historical commune codes.

### France outputs

Folder:

- `data/processed/france_lau_insee_documentation/`

Main files:

- `fr_lau_insee_lookup.csv`
- `fr_lau_insee_lookup_documentation.csv`
- `fr_old_insee_to_current_mapping.csv`
- `fr_old_insee_to_current_update_ready.csv`
- `france_lau_insee_nuts3_mapping.xlsx`

## 11. How to Run the France Harmonization

From the project root:

```bash
python src/france_lau_to_insee.py \
  --lau data/raw/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/raw/NUTS_RG_01M_2024_4326.gpkg \
  --adminexpress data/raw/adminexpress-cog-simpl-000-2025.gpkg \
  --commune-history data/raw/insee_history/v_commune_depuis_1943.csv \
  --commune-movements data/raw/insee_history/v_mvt_commune_2025.csv \
  --out-dir data/processed/france_lau_insee_documentation
```

If you want the France event table too, provide the Europe canonical output:

This is the normal production path when you want a France event table that is
directly comparable with French commune-based datasets such as Gaspar.

Important note about the internal logic:

- `events_lau_long.csv` from the Europe pipeline already contains
  `nuts0_code` to `nuts3_name`
- the France lookup also carries `nuts3_code` and `nuts3_name`
- the script now merges these safely by keeping the Europe event-table NUTS
  columns as canonical and using France lookup values only as fallback

Expected main output:

- `data/processed/france_lau_insee_documentation/events_fr_insee_long.csv`

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

## 12. Point-Level Flood Check Against JRC Events

Script:

- `src/check_points_against_jrc_floods.py`

Purpose:

- start from an Excel workbook of latitude / longitude points
- map each point to a LAU polygon
- use the processed JRC LAU event table as a fast prefilter
- inspect only the relevant official TIFF rasters for those candidate events
- return a clear point-level flood flag plus event-specific local flood metrics

This is the recommended workflow for:

- city-centre test points
- insured assets
- customer locations
- large address portfolios after geocoding

### Default inputs

- `data/raw/france_20_gps_google_maps.xlsx`
- `data/raw/LAU_RG_01M_2024_4326.gpkg`
- `data/processed/_outputs_eurostat_full/events_lau_long.parquet`
- `data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv`
- `data/JRC_flood_depth_maps/`

### Why the workflow is fast

The script does not compare every point against every TIFF.

It uses two stages:

1. Administrative prefilter
   - detect the Excel header row
   - read latitude / longitude points
   - map each point to its official Eurostat LAU polygon
   - enrich French points with INSEE / department / NUTS3 fields when available
2. Local flood check
   - keep only JRC events whose `lau_code` matches the point's LAU
   - open only those candidate rasters
   - sample the exact point pixel
   - inspect a local circular buffer around the point, default `2 km`

This makes the script scalable when the point list grows from a few examples to hundreds of addresses.

Boundary caveat:

- the administrative prefilter depends on the processed JRC LAU event table
- that table was created with the conservative default `all_touched=False`
- therefore, a border pixel that only lightly overlaps a LAU may be absent from that LAU in the precomputed table
- in those cases, the point workflow may skip a TIFF that is geographically close to the point but not recorded under the point's own LAU

### Local flood indicators

For each `point x candidate event`, the script can derive:

- exact point depth in cm
- whether a flood hit exists exactly at the point
- whether a flood hit exists within the local buffer
- flooded pixel count in the buffer
- flooded area in the buffer
- maximum, median, and mean flood depth in the buffer
- start and end dates of the matching JRC event
- raster filename used for the check

The script ignores:

- raster `nodata`
- the JRC permanent / seasonal water value `9999`
- flood cells at or below the chosen threshold

### Output workbook

Default output:

- `data/processed/france_points_jrc_flood_check.xlsx`

The workbook contains three sheets:

- `point_summary`
- `candidate_events`
- `event_hits`

#### `point_summary`

One row per input point.

Important fields:

- original point columns from the source Excel
- `lau_matched`
- `lau_touched_by_any_jrc_event`
- `jrc_flood_hit`
- `jrc_flood_flag`
- `candidate_event_count`
- `hit_event_count`
- `max_exact_point_depth_cm`
- `max_buffer_depth_cm`
- `max_buffer_median_depth_cm`
- `max_buffer_mean_depth_cm`
- `first_hit_start_date`
- `last_hit_end_date`
- `decision_path`
- `notes`

Interpretation:

- `lau_matched = False` means the point does not fall inside any supplied LAU polygon
- `lau_touched_by_any_jrc_event = False` means the point has a valid LAU but that LAU never appears in the processed JRC event table
- `jrc_flood_hit = False` means candidate events existed for that LAU but no flooded pixel above threshold was found at the point or in the local buffer
- `jrc_flood_hit = True` means at least one JRC event produced flooded pixels above threshold at the point or inside the local buffer

#### `candidate_events`

One row per `point x candidate JRC event`.

Useful fields:

- point metadata
- LAU / INSEE / NUTS3 metadata
- `event_id`
- `raster_file`
- `resolved_raster_path`
- `start_date`
- `end_date`
- `max_depth_cm`
- `flooded_pixels`
- `flooded_area_m2`
- `hit_at_point`
- `exact_point_depth_cm`
- `buffer_flood_hit`
- `buffer_max_depth_cm`
- `buffer_median_depth_cm`
- `buffer_mean_depth_cm`

#### `event_hits`

This is the filtered subset of `candidate_events` where:

- `hit_at_point = True`
- or `buffer_flood_hit = True`

### How to run it

Basic run:

```bash
python src/check_points_against_jrc_floods.py
```

Example with a study period and a stricter local flood definition:

```bash
python src/check_points_against_jrc_floods.py \
  --study-start 2018-01-01 \
  --study-end 2024-12-31 \
  --buffer-km 2 \
  --threshold-cm 10 \
  --out-file data/processed/france_points_jrc_flood_check_2018_2024.xlsx
```

### Main parameters

- `--points-file`
- `--sheet-name`
- `--latitude-col`
- `--longitude-col`
- `--point-id-col`
- `--city-col`
- `--lau-file`
- `--lau-country-filter`
- `--events-file`
- `--flood-dir`
- `--france-lookup-file`
- `--study-start`
- `--study-end`
- `--buffer-km`
- `--threshold-cm`
- `--out-file`

### Recommended interpretation

Use the point workflow as a screening layer:

- if the LAU is never touched in the processed JRC table, the point can safely be flagged as no JRC flood hit
- if the LAU is touched, the raster check is still necessary because the point may sit outside the flooded pixels
- buffer-based indicators are often more useful than the exact pixel alone because address coordinates and flood masks both contain some positional uncertainty

## 13. TIFF Visualization Logic

Notebook:

- `src/5_Visualize_Flood_TIFF_Map.ipynb`

Shared logic:

- `src/flood_preview.py`

The TIFFs are heavy, so the notebook does not try to display the full raster at full native resolution immediately.

Instead it uses:

1. A coarse scan of the whole raster to locate flood cells.
2. A detailed local crop around the flood.
3. Three interactive display paths:
   - exact native 20 m cells for sparse floods
   - preview-grid polygon cells for medium-size floods
   - raster overlay for broad qualitative previews
4. When a web-map raster overlay is used, the cropped preview is reprojected before display, but the result is still an approximation.

The dashboard does not use a different map algorithm.

It calls the same preview engine from `src/flood_preview.py`, which was extracted from the notebook logic.

For a full beginner-friendly walkthrough of the Streamlit display process, including how a `90,000 x 90,000` TIFF becomes a `1,800 x 1,800` preview and what `merged preview polygons` means, see [docs/streamlit_raster_dashboard_deep_guide.md](/D:/M2_MoSEF/DataCollection/docs/streamlit_raster_dashboard_deep_guide.md).

So the structure is:

- `src/5_Visualize_Flood_TIFF_Map.ipynb` = notebook interface
- `src/flood_preview.py` = shared preview engine
- `src/app.py` = dashboard interface built on the same engine

### Why this approach was chosen

If you draw every native 20 m cell for a large flood, the notebook and browser become slow.

If you draw only a full-raster image overlay, tiny floods become hard to see.

If you place a projected raster preview directly on a web map without reprojection, coastal pixels can appear shifted offshore.

Even after reprojection, a simple image overlay can still drift visually on a web map over large extents, because the browser stretches one rectangular image in map space instead of drawing each flood cell as its own geometry.

So the notebook balances:

- correctness
- speed
- map readability

### Streamlit rendering modes

The Streamlit dashboard now exposes three user-facing choices:

- `Auto`
- `Polygon pixels`
- `Raster overlay`

Internally, the shared engine in `src/flood_preview.py` can use three rendering strategies:

- `pixels`: exact native source cells when the event is sparse enough
- `preview_pixels`: polygons built from the downsampled preview grid when exact native cells would be too many for the browser
- `raster`: one image overlay for the preview crop

#### Exact native pixels

This mode reads real source cells from the TIFF and converts each visible cell corner from the flood CRS into latitude/longitude before drawing the polygon.

Advantages:

- best spatial faithfulness
- safest choice for coastlines and detailed inspection

Tradeoff:

- can be slow when the event contains many flooded cells

#### Preview-grid polygon pixels

This mode uses the already computed preview crop instead of the full native raster.

Each visible preview cell is still drawn as a polygon, so the browser sees real map geometry rather than one stretched image.

This is now the main compromise mode in the dashboard because it keeps the good alignment of polygon rendering while staying much faster than drawing all native 20 m cells.

Implementation note:

- adjacent preview cells with the same color bin are merged into row runs before drawing
- the Leaflet map is configured with canvas-preferred vector rendering to reduce browser overhead

#### Raster overlay

This mode converts the preview crop into one colored image and places that image on the web map.

Advantages:

- fastest to draw
- smallest browser workload

Tradeoff:

- it is the least trustworthy mode for exact alignment
- over large projected extents it can look slightly shifted north/south or offshore compared with polygon-based rendering and external viewers such as Felt

So the practical recommendation is:

- use `Auto` for general browsing
- use `Polygon pixels` when spatial alignment matters
- use `Raster overlay` only for fast qualitative overview

### Important caveat for coastal pixels and broad extents

If a few flooded cells appear slightly offshore or slightly north/south of the expected location:

- that can be a visualization artifact if the display method is too coarse
- but it can also come from the raster source itself or from basemap shoreline generalization

That is why the notebook and dashboard keep polygon-based modes based on actual source or preview cells.

## 14. Common Pitfalls

### Pitfall 1. Running `.py` directly in Bash

Wrong:

```bash
src/granular_tabularization.py
```

Correct:

```bash
python src/granular_tabularization.py
```

### Pitfall 2. Mixing raw rasters and display derivatives

Prefer:

- `data/JRC_flood_depth_maps/`

This is the cleanest source.

### Pitfall 3. Assuming every event should intersect a LAU

Not true.

Some events are outside the LAU coverage of the Eurostat file.

### Pitfall 4. Assuming all national codes are stable over time

Not true for France.

Historical commune codes can merge, split, or become delegated communes.

That is why the historical update table exists.

## 15. Recommended Workflow

For Europe:

1. Run `src/granular_tabularization.py` on `data/JRC_flood_depth_maps/`.
2. Check `run_metadata.json`.
3. Use `events_lau_long.csv` as the canonical analytical table.
4. Use NUTS outputs only as rollups, not as the main working table.

For France:

1. Run the Europe pipeline first.
2. Run `src/france_lau_to_insee.py`.
3. Use `src/check_points_against_jrc_floods.py` when you want to screen individual coordinates or address portfolios against JRC flood events.
4. Use `fr_old_insee_to_current_update_ready.csv` for old-code source updating.
5. Use `france_lau_insee_nuts3_mapping.xlsx` for documentation and manual review.

For visualization:

1. Open `src/5_Visualize_Flood_TIFF_Map.ipynb`.
2. Set `TIF_PATH`.
3. Use the default efficient workflow.
4. Switch to exact native pixel mode when you need detailed coastal inspection.
5. For browsing many rasters by year, run the dashboard with `streamlit run src/app.py`.

## 16. Raster Dashboard

The notebook is best when you already know which TIFF you want.

The Streamlit dashboard is better when you want to:

- browse rasters year by year
- filter filenames quickly
- compare several events in one session
- keep the efficient preview logic without editing notebook cells

Why Streamlit was chosen:

- it is simple for non-geospatial users
- it works well with heavy rasters when the expensive logic is cached
- it can embed the Folium web map directly in the page
- it keeps the workflow reproducible because the controls are visible

Run it from the project root:

```bash
streamlit run src/app.py
```

If `streamlit` is not recognized:

```bash
python -m streamlit run src/app.py
```

The dashboard:

- lists only official JRC TIFFs that match the README naming convention
- groups browsing by year
- uses the same two-stage preview logic as the notebook through `src/flood_preview.py`
- supports `auto`, `Polygon pixels`, and `Raster overlay` rendering modes
- uses polygon-based rendering as the safer default path for many coastal and medium-size events
- lets you download the current interactive map as HTML
- replaces the old scratch `app.py` logic with the notebook-based workflow

Recommended use:

- keep `Auto` for most browsing sessions
- switch to `Polygon pixels` for coastlines, estuaries, and alignment checks against Felt or other viewers
- switch to `Raster overlay` only when you need the lightest possible browser rendering and can accept approximate placement

For the full dashboard internals in plain language, see [docs/streamlit_raster_dashboard_deep_guide.md](/D:/M2_MoSEF/DataCollection/docs/streamlit_raster_dashboard_deep_guide.md).

## 17. Compare France JRC vs Gaspar

Script:

- `src/compare_france_jrc_gaspar.py`

Purpose:

- compare the France JRC commune-event table with the cleaned Gaspar flood table
- match at commune level using normalized INSEE commune codes
- allow a flexible `7` day window on both start and end dates

Why the Gaspar event key is not just `cod_nat_catnat`:

- in the cleaned Gaspar sheet, one `cod_nat_catnat` can appear with multiple
  `dat_deb` / `dat_fin` pairs
- for comparison with JRC time intervals, the script therefore defines:
  - `gaspar_event_uid = cod_nat_catnat + dat_deb + dat_fin`

Primary matching rule:

- same normalized commune code
- `abs(jrc_start_date - gaspar_dat_deb) <= 7`
- `abs(jrc_end_date - gaspar_dat_fin) <= 7`

Top-level outputs to open first:

- `comparison_guide.md`
- `comparison_summary.csv`
- `comparison_summary.xlsx`
- `coverage_overview.csv`
- `coverage_overview.xlsx`
- `best_match_overview_commune.csv`
- `best_match_overview_commune.xlsx`
- `jrc_gaspar_comparison.xlsx`

Detailed audit outputs:

- all canonical tables, raw match tables, unmatched tables, parquet files, and diagnostics are written to `details/`
- this keeps the comparison folder readable while preserving the full audit trail

Run:

```bash
python src/compare_france_jrc_gaspar.py \
  --jrc-file data/processed/france_lau_insee_documentation/events_fr_insee_long.csv \
  --gaspar-file data/processed/Gaspar_2015_2024.xlsx \
  --sheet-name Gaspar20152024FloodsClean \
  --date-window-days 7 \
  --out-dir data/processed/jrc_gaspar_comparison_7d
```

### Flexible 30-day variant with department outputs

Script:

- `src/compare_france_jrc_gaspar_flexible.py`

Purpose:

- keep the same JRC France commune-event input and the same cleaned Gaspar input
- use a broader default date window of `30` days
- keep commune-level matching outputs
- add department-level rollups and department-level match outputs

Why this second script exists:

- the strict `7` day script is useful when you want a conservative commune-event match
- but some JRC and Gaspar records can still describe the same flood episode with more timing drift
- a broader comparison is useful for exploratory matching and event-family review

Flexible commune-level date logic:

- same normalized commune code
- and at least one of the following:
  - `abs(jrc_start_date - gaspar_start_date) <= 30` and `abs(jrc_end_date - gaspar_end_date) <= 30`
  - `abs(jrc_start_date - gaspar_end_date) <= 30` and `abs(gaspar_start_date - jrc_end_date) <= 30`
  - the two date intervals still overlap after both sides are expanded by the same `30` day window

Important interpretation:

- the first rule is the original aligned start/start and end/end comparison, just with a larger window
- the second rule is the new cross-date condition
- the third rule keeps events that are still close once the intervals are buffered

Department-level logic:

- department codes are derived from commune INSEE codes
- JRC department outputs aggregate the France commune-event table by:
  - `jrc_event_id`
  - `department_code`
  - `jrc_start_date`
  - `jrc_end_date`
- Gaspar department outputs aggregate by:
  - `gaspar_event_uid`
  - `department_code`
  - `gaspar_start_date`
  - `gaspar_end_date`
- Gaspar department rows receive `dept_ref_nuts3_code` and `dept_ref_nuts3_name`
  from the full France LAU -> INSEE lookup, so departments such as `2A` and `2B`
  keep their NUTS3 labels even when no JRC event rows exist there

Top-level outputs to open first:

- `comparison_guide.md`
- `comparison_summary.csv`
- `comparison_summary.xlsx`
- `coverage_overview.csv`
- `coverage_overview.xlsx`
- `best_match_overview_commune.csv`
- `best_match_overview_commune.xlsx`
- `best_match_overview_department.csv`
- `best_match_overview_department.xlsx`
- `jrc_gaspar_comparison_flexible.xlsx`
- `plots/`

Detailed audit outputs:

- all canonical tables, raw match tables, unmatched tables, parquet files, department reference tables, and diagnostics are written to `details/`
- the plotting script reads those detailed files automatically, so the top-level folder can stay concise

Plotting script:

- `src/plot_france_jrc_gaspar_comparison.py`

Plot outputs:

- `plots/comparison_overview.png`
- `plots/commune_level_summary.png`
- `plots/department_level_summary.png`
- `plots/commune_event_summary.png`
- `plots/department_event_summary.png`
- `plots/plot_manifest.json`

Run plotting:

```bash
python src/plot_france_jrc_gaspar_comparison.py \
  --comparison-dir data/processed/jrc_gaspar_comparison_flexible_30d
```

Run:

```bash
python src/compare_france_jrc_gaspar_flexible.py \
  --jrc-file data/processed/france_lau_insee_documentation/events_fr_insee_long.csv \
  --gaspar-file data/processed/Gaspar_2015_2024.xlsx \
  --sheet-name Gaspar20152024FloodsClean \
  --date-window-days 30 \
  --out-dir data/processed/jrc_gaspar_comparison_flexible_30d
```

## 18. Final Mental Model

The simplest way to think about the project is:

- the TIFF is the physical flood signal
- LAU polygons are the first administrative unit we trust across Europe
- NUTS levels are aggregations of LAU
- France then needs a second harmonization step to match national coding systems

So the workflow is not:

"Make one perfect all-purpose geodata file."

It is:

1. Build one strong Europe-wide administrative flood table at LAU level.
2. Aggregate it to NUTS when needed.
3. Harmonize to country-specific coding systems only in a second step.

That separation is one of the main reasons the current pipeline is more robust than the earlier notebook-based approach.
