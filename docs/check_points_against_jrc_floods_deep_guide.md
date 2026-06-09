# Deep Guide: How `check_points_against_jrc_floods.py` Works

This document explains the logic of `src/check_points_against_jrc_floods.py` in detail.

It is meant for cases where you want to understand:

- how the script reads an Excel workbook of latitude / longitude points
- how those points are mapped to official Eurostat LAU polygons
- how the script narrows down candidate JRC flood events
- how the final TIFF inspection works
- what the output fields really mean
- where the main limitations and false-negative risks come from

## 1. Purpose

The script is a point-level flood screening workflow.

It answers a question like:

> For each coordinate in my workbook, is there evidence that at least one official JRC flood event affected the local `40 m` point area or the nearby `1 km` surrounding area?

The script is designed to be much faster than checking every point against every TIFF.

It uses two stages:

1. Administrative prefilter:
   map each point to a LAU and keep only JRC events already linked to that LAU.
2. Raster confirmation:
   open only those candidate TIFFs and inspect both the `40 m` point buffer and the `1 km` surrounding buffer.

So the final decision is still raster-based, but the script uses the tabular LAU event table to reduce the search space first.

## 2. What The Script Needs

The main defaults are:

- points workbook: `data/raw/france_20_gps_google_maps.xlsx`
- processed JRC LAU event table: `data/processed/_outputs_eurostat_full/events_lau_long.parquet`
- Eurostat LAU polygons: `data/raw/LAU_RG_01M_2024_4326.gpkg`
- JRC TIFF root: `data/JRC_flood_depth_maps`
- France enrichment lookup: `data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv`
- output workbook: `data/processed/france_points_jrc_flood_check.xlsx`

Important assumptions:

- input coordinates are WGS84 latitude / longitude in decimal degrees
- longitude is the X coordinate
- latitude is the Y coordinate
- the processed JRC event table was already created by `src/granular_tabularization.py`

## 3. High-Level Flow

The execution path inside `main()` is:

1. Load the Excel workbook of points.
2. Optionally derive a row-level study window for each point row.
3. Load the LAU polygon layer.
4. Convert the tabular coordinates into geospatial point geometries.
5. Spatially join points to LAU polygons.
6. Optionally enrich French matches with INSEE and NUTS3 fields.
7. Load the processed LAU event table and keep only events for the mapped LAUs.
8. Optionally filter those events by one global study period.
9. Expand the points into `point x candidate-event` rows and optionally filter those rows again with row-level date windows.
10. Resolve candidate TIFF file paths.
11. Open only those candidate TIFFs and inspect the `40 m` point buffer and the `1 km` surrounding buffer.
12. Build three output sheets and write an Excel workbook.

## 4. Step-By-Step Logic

### Step 1. Detect the Excel header row

Function: `detect_header_row()`

The script does not assume the header is always on the first row.

It scans the first 25 rows and normalizes text by:

- trimming spaces
- lowercasing
- keeping only alphanumeric characters and `#`

It then looks for a row containing both `latitude` and `longitude`.

If `sheet_name` is omitted, pandas may return all sheets as a dictionary. The script now handles that case and uses the first sheet.

If no row clearly contains both labels, the script falls back to header row `0`.

### Step 2. Read and normalize the points table

Function: `load_points_table()`

After choosing the header row, the script reads the sheet into a DataFrame and:

- drops rows that are entirely empty
- trims column names
- creates `excel_row_number` so you can trace each output row back to the source workbook

The script then resolves column names using aliases:

- latitude: `Latitude`, `Lat`, `Y`
- longitude: `Longitude`, `Long`, `Lon`, `Lng`, `X`
- point ID: `#`, `id`, `point_id`
- optional label column: `City`, `Commune`, `Address`, `Location`

If no point ID column exists, it creates a sequential `point_id` column.

If no city-like label exists, the script still runs normally.

The city column is only for readability in the outputs. It does not affect flood matching.

Finally, latitude and longitude are coerced to numeric values. Rows with invalid or missing coordinates are dropped.

The coordinate parsing is handled by:

- `load_points_table()`
- which calls `parse_coordinate_series()`
- which uses `normalize_decimal_text()` to accept both decimal dots and decimal commas

So values like:

- `47.87431063`
- `47,87431063`

are both accepted as valid coordinates.

This means workbook columns like:

- `LAT`
- `LONG`

are now accepted directly.

### Step 3. Optionally derive one study window per row

Function: `build_row_level_study_periods()`

The script can now build a separate study window for each workbook row.

This is the important new behavior used for the T20 portfolio logic.

The rule is:

- `study_period_start = full history` by default
- `study_period_end = primary_end_date`
- if the primary end date is missing, use the fallback end date

For the T20 workbook, the intended mapping is:

- anchor date = `Reference_Date`
- primary end = `Closed_Default_Date`
- fallback end = `Cut_off_Date`

So for example:

- `Reference_Date = 31/12/2008`
- `Closed_Default_Date = 08/10/2013`

becomes:

- `study_period_start = open / unbounded`
- `study_period_end = 08/10/2013`

If `Closed_Default_Date` is empty, the same row keeps the same full-history start logic and uses `Cut_off_Date` as the end instead.

If you explicitly pass `--row-study-lookback-years`, the script can still switch back to:

- `study_period_start = anchor_date - lookback_years`

The script also stores these derived fields for traceability:

- `study_period_anchor_date`
- `study_period_primary_end_date`
- `study_period_fallback_end_date`
- `study_period_start`
- `study_period_end`
- `study_period_end_source`

### Step 4. Turn rows into geometries

Function: `build_points_gdf()`

Each point row is converted into a geometry using:

- `x = longitude`
- `y = latitude`

The result is a GeoDataFrame in CRS `EPSG:4326`.

This means a row like:

- latitude `48.8566`
- longitude `2.3522`

becomes a geospatial point like:

- `Point(2.3522, 48.8566)`

If latitude and longitude are swapped in the workbook, the mapping will be wrong.

### Step 5. Load the official LAU polygons

Function: `load_lau()` from `src/granular_tabularization.py`

The script loads the LAU GeoPackage and standardizes the official Eurostat columns:

- `GISCO_ID` -> `lau_code`
- `CNTR_CODE` -> `country_code`
- `LAU_NAME` -> `lau_name`

It also:

- ensures the geometry CRS is `EPSG:4326`
- creates `lau_code_local` by stripping the leading country prefix
- optionally filters the LAU layer to the requested countries
- keeps only the relevant geometry and lookup columns
- repairs invalid geometries where possible

So by the time point matching happens, the LAU polygons are cleaned and standardized.

### Step 6. Map each point to a LAU polygon

Function: `map_points_to_lau()`

This is the first real spatial matching step.

The script performs a spatial join with:

- `how="left"`
- `predicate="within"`

Meaning:

- keep every point row
- if a point is inside a LAU polygon, attach that polygon's fields to the point

Those attached fields include:

- `lau_code`
- `lau_code_local`
- `lau_name`
- `country_code`
- optional `population_2024`
- optional `area_km2`

If a point is not matched with `within`, the script tries a fallback spatial join with `predicate="intersects"`.

Why the fallback exists:

- a point exactly on a border may fail `within`
- `intersects` can recover some boundary cases

This is still a best-effort assignment. Border points remain inherently delicate.

### Step 7. Attach the France-specific enrichment

Function: `attach_france_lookup()`

After LAU matching, the script optionally merges a France lookup table by `lau_code`.

This adds administrative fields such as:

- `insee_com`
- `commune_name_adminexpress`
- `insee_dep`
- `insee_reg`
- `nuts3_code`
- `nuts3_name`

These fields are for reporting and downstream interpretation. They do not determine the initial point-to-LAU match.

### Step 8. Build the list of target LAUs

After the spatial join, the script collects the set of unique matched `lau_code` values from the points.

This set is the input to the next stage.

If a point has no matched LAU, it does not contribute any `lau_code` to the event prefilter.

### Step 9. Load the processed LAU event table

Function: `load_lau_events()`

The script reads the processed event table from parquet or CSV and checks that the expected columns exist.

Then it immediately filters the table to:

- only rows whose `lau_code` is in the set found under the supplied points

This is the core prefilter.

It is what makes the workflow scalable:

- without it, each point would need to be checked against every TIFF
- with it, only events already known to have touched the same LAU are considered

The script also:

- parses `start_date`
- parses `end_date`
- drops duplicate `(event_id, lau_code)` pairs

### Step 10. Apply optional global study-period filtering

Function: `filter_events_by_study_period()`

If `--study-start` or `--study-end` are provided, the script keeps only events whose date intervals overlap the requested study window.

The logic is interval overlap, not strict containment.

That means:

- if `study_start` is set, an event is kept only if `end_date >= study_start`
- if `study_end` is set, an event is kept only if `start_date <= study_end`

So events that partially overlap the study period are still retained.

This filter is still useful when you want one broad time window shared by the entire workbook.

### Step 11. Expand points into point x candidate-event rows

Inside `main()`, the script merges:

- the point metadata
- the filtered LAU event rows

on `lau_code`.

This creates a candidate table where each row is:

- one point
- one candidate JRC event for that point's LAU

At this stage the script has not yet confirmed local flooding at the point. It has only said:

> This event is worth checking because it touched the same LAU.

If row-level study fields exist, they are carried into this candidate table.

### Step 12. Apply optional row-level study-window filtering

Function: `filter_candidate_events_by_row_study_period()`

This is the main new temporal step for the T20 process.

The script checks interval overlap separately for each candidate row.

A candidate event is kept when:

- `event_end >= row_study_period_start`
- and `event_start <= row_study_period_end`

In plain language:

- all historical floods before default are kept by default
- floods during the default period are also kept
- floods fully outside that row-specific window are dropped

This keeps the logic simple:

1. spatial prefilter by LAU
2. temporal prefilter by row-specific interval overlap
3. raster confirmation only for survivors

### Step 13. Resolve the TIFF path for each candidate event

Function: `resolve_raster_paths()`

The event table may already contain a usable `raster_path`. If that path exists, the script uses it.

Otherwise it tries several likely locations:

- `flood_dir / year / raster_file`
- `flood_dir / year_filtered / raster_file`
- `flood_dir / raster_file`
- recursive search under `flood_dir`

The result is stored in:

- `resolved_raster_path`
- `raster_path_found`

If `raster_path_found = False`, the event stays in the candidate table but cannot be locally inspected in the raster stage.

### Step 14. Inspect only the candidate TIFFs

Function: `inspect_candidate_events()`

This is the second stage.

The script keeps only candidates where:

- `event_id` exists
- `raster_path_found = True`

It then groups those rows by `resolved_raster_path`.

Why group by raster path:

- several points may refer to the same event TIFF
- opening the raster once per group is more efficient than reopening it for each row

For each TIFF:

1. open the raster with rasterio
2. create a coordinate transformer from `EPSG:4326` to the raster CRS
3. transform the point's longitude / latitude into raster coordinates
4. check the local `40 m` point buffer
5. check the `1 km` surrounding buffer

This is the true raster confirmation stage.

## 5. 40 m Point Buffer Check

Inside `inspect_candidate_events()`, the script first builds the local point-area buffer.

Default:

- radius `40 m`

The script uses:

- `Point(x, y).buffer(point_buffer_m)`

and computes flooded-pixel statistics only for pixels:

- touched by that `40 m` circle
- not masked
- not raster `nodata`
- not JRC permanent water code `9999`
- strictly above `threshold_cm`

Important naming detail:

- `hit_at_point`
- `hit_at_point_event_count`

are now local `40 m` buffer metrics for backwards compatibility with the earlier workbook outputs

They no longer mean "one exact raster pixel under the coordinate".

The `40 m` outputs include:

- `point_buffer_total_pixels`
- `point_buffer_flood_hit`
- `point_buffer_flooded_pixels`
- `point_buffer_flooded_pixel_pct`
- `point_buffer_flooded_area_m2`
- `point_buffer_min_depth_cm`
- `point_buffer_max_depth_cm`
- `point_buffer_median_depth_cm`
- `point_buffer_mean_depth_cm`

The legacy alias:

- `exact_point_depth_cm`

now mirrors `point_buffer_max_depth_cm` so older downstream reads do not break.

## 6. 1 km Surrounding Buffer Check

Function: `compute_buffer_stats()`

The broader buffer is a second circular search area around the same point.

Default:

- radius `1 km`

The script converts `buffer_km` into meters and creates a geometry:

- `Point(x, y).buffer(radius_m)`

Then it:

1. computes the smallest raster window covering that buffer
2. reads the raster data for that window
3. builds a mask of pixels inside the circle
4. filters out invalid cells
5. keeps only cells with depth strictly greater than the threshold

The buffer mask uses:

- `all_touched=True`

Meaning:

- a raster cell can count if the buffer circle touches any part of that cell

This is intentionally more inclusive than the conservative admin tabularization logic.

If no valid flooded pixels are found in the buffer, the result is:

- `buffer_flood_hit = False`
- zero flooded pixels
- zero flooded area

If valid flooded pixels are found, the script computes:

- `buffer_total_pixels`
- `buffer_flood_hit`
- `buffer_flooded_pixels`
- `buffer_flooded_pixel_pct`
- `buffer_flooded_area_m2`
- `buffer_min_depth_cm`
- `buffer_max_depth_cm`
- `buffer_median_depth_cm`
- `buffer_mean_depth_cm`

The flooded-pixel percentage is:

- `100 * flooded_pixels / total_pixels`

where `total_pixels` means the raster pixels touched by the buffer and available for evaluation after masking and `nodata` removal.

Important nuance:

- the `40 m` point buffer and the `1 km` surrounding buffer are not the same thing
- the local `40 m` area can stay dry while the wider `1 km` neighborhood still shows flooding
- any `40 m` hit will usually also imply a `1 km` hit, but not the reverse

## 7. How Flood Positives Are Defined

For a candidate event, the script treats the event as a positive local hit if either is true:

- `point_buffer_flood_hit = True`
- `surrounding_buffer_flood_hit = True`

That positive logic is later used for:

- the `event_hits` output sheet
- `hit_event_count`
- `jrc_flood_hit`
- `jrc_flood_flag`

So the final screening decision is not limited to exact-pixel hits.

## 8. Output Workbook Structure

The script writes three sheets.

### `point_summary`

One row per original point.

This is the high-level decision table.

It contains:

- original source columns
- the matched LAU / INSEE / NUTS metadata
- candidate event counts
- checked event counts
- hit counters
- maximum flood metrics for both buffer scales
- date range of the positive hits
- decision flags and notes

Important summary fields:

- `lau_matched`
- `lau_touched_by_any_jrc_event`
- `candidate_event_count`
- `checked_event_count`
- `hit_at_point_event_count`
- `hit_within_buffer_event_count`
- `hit_event_count_until_default_date`
- `max_point_buffer_depth_cm`
- `max_buffer_depth_cm`
- `hit_event_count`
- `jrc_flood_hit`
- `jrc_flood_flag`
- `decision_path`
- `notes`
- `study_period_start`
- `study_period_end`

If row-level study windows are used, `study_period_start` and `study_period_end` are row-specific values derived from the workbook, not one shared CLI date range.

Meaning of the main counters:

- `candidate_event_count`:
  how many candidate JRC events were found for the point's LAU
- `checked_event_count`:
  how many of those candidates were actually inspected in rasters
- `hit_at_point_event_count`:
  how many candidate events had flooded pixels inside the `40 m` point buffer
- `hit_within_buffer_event_count`:
  how many candidate events had flooded pixels somewhere inside the `1 km` surrounding buffer
- `hit_event_count`:
  how many candidate events were positive under the final rule of `40 m` point-buffer hit or `1 km` surrounding-buffer hit, inside the main row window that ends at `Closed_Default_Date` or falls back to `Cut_off_Date`
- `hit_event_count_until_default_date`:
  how many positive matched flood events were found from the past up to the default-start date, which in this workflow is `Reference_Date`

This extra count is only a summary feature.

It does not change:

- the main candidate-event filter
- `hit_event_count`
- `jrc_flood_hit`

### `candidate_events`

One row per point x candidate-event pair.

This is the main diagnostics sheet if you want to inspect event-level detail.

It includes:

- point metadata
- LAU / INSEE / NUTS3 metadata
- raw workbook date columns when used, for example `Reference_Date`, `Closed_Default_Date`, `Cut_off_Date`
- derived row-level study fields
- event metadata
- resolved raster path
- whether the raster path was found
- `40 m` point-buffer hit result
- `1 km` surrounding-buffer hit result
- both sets of depth metrics, including `min`
- flooded-pixel percentages and total buffer-pixel counts

### `event_hits`

This is the subset of `candidate_events` where:

- `point_buffer_flood_hit = True`
- or `surrounding_buffer_flood_hit = True`

It is the easiest sheet to use when you only want positive detections.

For the current simplified output-column dictionary, see:

- `docs/flood_workbook_column_dictionary.md`

## 9. Meaning of the Final Decision Flags

The summary table sets:

- `jrc_flood_hit = hit_event_count > 0`
- `jrc_flood_flag = "yes"` if true, otherwise `"no"`

The script also creates `decision_path` and `notes` to explain why a point got its result.

The main paths are:

- `point_outside_lau`
- `lau_not_touched_in_processed_jrc_events`
- `candidate_events_checked_but_no_local_flood_pixel`
- `positive_local_flood_hit`

These are useful because "no" can mean several different things:

- the point was outside the LAU layer
- the point's LAU had no candidate JRC events
- candidate JRC events existed, but both the `40 m` point buffer and the `1 km` surrounding buffer were dry

## 10. Why This Workflow Is Fast

The performance gain mainly comes from the LAU prefilter.

Instead of:

- every point x every TIFF

the script does:

- every point -> one LAU
- that LAU -> only its candidate events
- only those events -> raster confirmation

It also saves time by:

- grouping candidate rows by raster path before opening the TIFF
- resolving and caching raster paths
- reading only a local raster window for the buffer instead of the full raster

This is why the script scales much better once you move from a few points to hundreds of points.

## 11. Important Limitations

### Limitation 1. The prefilter is LAU-based

The candidate-event search is limited to events already recorded for the point's own LAU.

So the main false-negative risk is:

- a nearby flood exists
- but it was recorded under a neighboring LAU rather than the point's LAU
- therefore that event is never opened as a candidate TIFF

This is most relevant for:

- points close to commune boundaries
- local buffers that extend across administrative borders

### Limitation 2. The precomputed LAU event table is conservative at boundaries

The canonical tabularization created by `src/granular_tabularization.py` uses conservative whole-pixel polygon logic by default.

That means:

- a border pixel that only slightly overlaps a LAU may be absent from that LAU in the event table

So the point workflow can inherit that strictness through the LAU prefilter.

### Limitation 3. CRS and coordinate quality still matter

The script assumes:

- latitude / longitude are correct
- they are in WGS84
- longitude and latitude are not swapped

If those assumptions are wrong, the LAU mapping and raster sampling can both be wrong.

### Limitation 4. `lau_country_filter` can exclude valid points

By default:

- `--lau-country-filter FR`

So if your workbook contains points outside France and you keep the default filter, those points may not match any LAU at all.

### Limitation 5. The workflow is a screening layer

The script is very useful for large batches of coordinates, but it is still a practical screening workflow, not a legal or hydrodynamic truth system.

If a point is especially important, you may still want to inspect the relevant TIFFs manually.

## 12. Recommended Use

Use this workflow when:

- you have tens, hundreds, or more coordinates
- you need a reproducible and scalable screening method
- you want event-level diagnostics, not just a yes / no answer

Be especially careful when:

- points lie near commune boundaries
- you need cross-border local search behavior
- input coordinates come from noisy geocoding
- you want a very strict interpretation of what counts as a hit

Good tuning levers are:

- `--lau-country-filter`
- `--study-start`
- `--study-end`
- `--row-study-anchor-col`
- `--row-study-end-col`
- `--row-study-end-fallback-col`
- `--row-study-lookback-years`
- `--point-buffer-m`
- `--buffer-km`
- `--threshold-cm`

## 13. Example Commands

Default run:

```bash
python src/check_points_against_jrc_floods.py
```

Use the first sheet explicitly:

```bash
python src/check_points_against_jrc_floods.py --sheet-name 0
```

Restrict the study period:

```bash
python src/check_points_against_jrc_floods.py \
  --study-start 2018-01-01 \
  --study-end 2024-12-31
```

Run the T20 row-level temporal logic with the new default full-history window:

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

If you want the older bounded lookback behavior:

```bash
python src/check_points_against_jrc_floods.py \
  --row-study-anchor-col Reference_Date \
  --row-study-end-col Closed_Default_Date \
  --row-study-end-fallback-col Cut_off_Date \
  --row-study-lookback-years 5
```

Change the surrounding buffer radius and flood threshold:

```bash
python src/check_points_against_jrc_floods.py \
  --point-buffer-m 40 \
  --buffer-km 1 \
  --threshold-cm 10
```

Run across several countries:

```bash
python src/check_points_against_jrc_floods.py \
  --lau-country-filter FR,BE,DE
```

## 14. Implementation Map

If you want to jump into the code quickly, these are the most important functions:

- `detect_header_row()`:
  find the real Excel header row
- `load_points_table()`:
  read and normalize the workbook
- `build_row_level_study_periods()`:
  derive one study window per row
- `build_points_gdf()`:
  create point geometries
- `map_points_to_lau()`:
  point-in-polygon LAU assignment
- `attach_france_lookup()`:
  add France INSEE / NUTS reporting fields
- `load_lau_events()`:
  load and prefilter the processed event table
- `filter_events_by_study_period()`:
  keep overlapping event intervals only
- `filter_candidate_events_by_row_study_period()`:
  keep only candidate events overlapping each row's own study window
- `resolve_raster_paths()`:
  locate the official TIFF for each candidate event
- `inspect_candidate_events()`:
  `40 m` point-buffer and `1 km` surrounding-buffer raster checks
- `compute_buffer_stats()`:
  reusable circular-buffer metrics for either scale
- `build_summary_table()`:
  point-level decision summary
- `build_candidate_sheet()`:
  point x candidate-event diagnostics
- `build_hits_sheet()`:
  positive event subset

## 15. Bottom Line

The script works by combining:

- a spatial admin lookup
- a precomputed event table
- direct raster confirmation

Its logic is:

1. find the point's LAU
2. find only JRC events already linked to that LAU
3. if needed, derive one study window per row from workbook dates
4. keep only candidate events whose intervals overlap that row-specific window
5. open only those TIFFs
6. confirm the `40 m` point buffer and the `1 km` surrounding buffer in the raster
7. summarize the result at point level and event level

That is why it is both practical and explainable for large coordinate portfolios.
