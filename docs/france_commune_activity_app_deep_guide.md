# Deep Guide: How The France Gaspar vs JRC Commune Activity App Works

This document explains the full logic of the France commune activity viewer in plain language.

It is written for cases where you want to understand:

- what happens after you launch the app
- how the app reads `Gaspar` and `JRC`
- how `cod_commune`, `INSEE`, `LAU`, and historical commune updates interact
- why some Gaspar rows are matched and some are unresolved
- how the time filters work
- how the commune map is built
- where to edit the code when you want to change behavior

The main code paths are:

- Streamlit UI: `src/gaspar_jrc_france_map_app.py`
- shared data engine: `src/france_commune_activity.py`
- launchers:
  - `run_gaspar_jrc_france_map.cmd`
  - `run_gaspar_jrc_france_map.ps1`
  - `run_gaspar_jrc_france_map.sh`

## 1. The Main Idea

The app answers this question:

> For one date, one month, one year, or one custom date range, which French communes are active in Gaspar, JRC, or both?

The app does not compare rasters directly on the map.

Instead, it works at the **commune table** level:

1. read a Gaspar commune-event table
2. convert Gaspar commune identifiers to current commune identifiers where possible
3. read a JRC France commune-event table
4. keep only rows whose event periods overlap the selected period
5. aggregate rows by current commune
6. join those aggregates to AdminExpress commune polygons
7. color the communes on a map of France

So the map is really a **temporal commune activity viewer**, not a raster viewer.

## 2. The Two Files You Should Read First

If you want to understand the code efficiently, read in this order:

1. `src/gaspar_jrc_france_map_app.py`
2. `src/france_commune_activity.py`

Why this order:

- the Streamlit file tells you what the user can choose
- the shared data file tells you how those choices are executed

Good mental split:

- `gaspar_jrc_france_map_app.py` = UI, caching, metrics, map rendering
- `france_commune_activity.py` = data loading, matching, filtering, aggregation

## 3. Startup Flow

When you run one of the launchers, the process is:

1. locate a usable Python interpreter
2. make sure `src/` and local packages are importable
3. start Streamlit
4. Streamlit imports `src/gaspar_jrc_france_map_app.py`
5. that file imports helpers from `src/france_commune_activity.py`
6. the `main()` function builds the app

The Streamlit entrypoint is:

- `main()` in `src/gaspar_jrc_france_map_app.py`

That is the best single function to read first.

## 4. Default Data Inputs

The shared module defines all default file locations near the top of:

- `src/france_commune_activity.py`

Important defaults:

- `data/processed/Gaspar_2015_2024.xlsx`
- `data/raw/catnat_gaspar.csv`
- `data/raw/catnat_gaspar.xlsx`
- `data/processed/france_lau_insee_documentation/events_fr_insee_long.csv`
- `data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv`
- `data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv`
- `data/raw/adminexpress-cog-simpl-000-2025.gpkg`

These correspond to three different needs:

- event rows from Gaspar
- event rows from JRC
- commune geometry plus reconciliation tables

## 5. File-Level Responsibilities

### `src/gaspar_jrc_france_map_app.py`

This file is responsible for:

- the sidebar controls
- choosing data source mode
- choosing time filter mode
- loading cached tables
- computing top-level metrics
- rendering the Folium map
- rendering tables and diagnostics

### `src/france_commune_activity.py`

This file is responsible for:

- reading CSV / Excel / parquet
- normalizing commune names
- building time periods
- filtering rows by overlapping time window
- loading France lookup tables
- resolving Gaspar commune codes to current communes
- preparing JRC commune rows
- loading commune polygons
- aggregating activity by commune
- combining Gaspar and JRC into comparison classes

## 6. Gaspar: Two Possible Inputs

The app supports two Gaspar modes from the sidebar:

- `Processed workbook`
- `Raw dataset (live transform)`

### Processed workbook mode

This uses:

- `prepare_processed_gaspar_rows()`

It reads:

- `data/processed/Gaspar_2015_2024.xlsx`
- sheet `Gaspar20152024FloodsClean`

This is the already cleaned dataset you produced earlier.

It creates standardized fields such as:

- `gaspar_start_date`
- `gaspar_end_date`
- `activity_start_date`
- `activity_end_date`
- `gaspar_event_uid`
- `gaspar_source_cod_commune`
- `gaspar_source_insee_com`

### Raw dataset mode

This uses:

- `prepare_raw_gaspar_rows()`

It reproduces the notebook-style transformation directly from raw Gaspar input:

1. read raw Gaspar
2. parse dates
3. keep the 2015 to 2024 period
4. keep flood-related risks only
5. keep the canonical columns
6. drop duplicate commune-event rows

The flood labels are defined in:

- `DEFAULT_GASPAR_FLOOD_RISK_LABELS`

So raw mode is a live reconstruction of the cleaned flood subset.

## 7. How Gaspar Commune Matching Works

This is the most important logic in the whole app.

The key function is:

- `resolve_gaspar_current_communes()`

Its job is:

> take a Gaspar row and attach a current commune `INSEE` code that the map can use

It follows this sequence:

1. exact current code match
2. historical old-INSEE to current-INSEE update
3. unique current commune-name match using AdminExpress names
4. unique current commune-name match using LAU names

If all four fail, the row remains unresolved.

### Step 1. Exact current code match

If `gaspar_source_insee_com` already exists in the current commune lookup, the row is marked:

- `gaspar_commune_match_method = current_code_exact`

This is the cleanest case.

### Step 2. Historical code update

If the Gaspar commune code is old, the app checks:

- `fr_old_insee_to_current_update_ready.csv`

If there is a safe update path, the row is marked:

- `gaspar_commune_match_method = historical_code_update_ready`

This is the main mechanism for commune history changes.

### Step 3. Unique AdminExpress name fallback

If the code did not resolve, the app normalizes the commune name and checks whether that normalized name uniquely identifies one current commune in AdminExpress.

If yes, the row is marked:

- `gaspar_commune_match_method = current_name_unique_adminexpress`

### Step 4. Unique LAU name fallback

If the AdminExpress name fallback fails, the app tries the same idea against LAU names.

If yes, the row is marked:

- `gaspar_commune_match_method = current_name_unique_lau`

### Final status field

At the end, the row gets:

- `gaspar_commune_match_found = True` if a current commune was assigned
- `False` otherwise

That single boolean drives:

- whether the row can appear on the map
- whether the row contributes to commune aggregates
- the `Matched Gaspar rows` and `Unresolved filtered Gaspar rows` metrics

## 8. Special Cases Such As Corsica

Corsica-style commune codes such as:

- `2A001`
- `2B246`

are preserved correctly because the normalization logic does **not** force commune codes to numeric-only format.

The app reuses the same commune-code normalization style used elsewhere in the repo:

- string-based
- uppercase
- strip trailing `.0`
- only zero-pad purely numeric codes

So:

- `39548` can be padded if needed
- `2B246` stays `2B246`

This matters for:

- Corsica
- other alphanumeric INSEE commune codes

## 9. Why Some Gaspar Rows Stay Unresolved

A row becomes unresolved when it is inside the chosen time filter but still cannot be attached to a current commune.

Typical causes:

- the Gaspar commune code is no longer current
- no safe old-to-current mapping is available
- the commune name is ambiguous
- the commune name does not uniquely match a current commune
- the code and the name both fail to map confidently

The app is conservative by design:

- it prefers dropping one uncertain row
- rather than drawing it in the wrong commune

That is why unresolved rows are excluded from the commune map.

## 10. How JRC Rows Are Prepared

JRC preparation is simpler because the processed France event table already contains current commune information.

The main function is:

- `prepare_jrc_activity_rows()`

It does the following:

1. read `events_fr_insee_long.csv`
2. keep only rows with successful `insee_match_found` if that column exists
3. normalize `insee_com`
4. parse `start_date` and `end_date`
5. create standardized activity fields:
   - `activity_start_date`
   - `activity_end_date`
6. deduplicate at the event-commune-date grain

So JRC is already close to map-ready once the France harmonization pipeline has been run.

## 11. Time Filtering Logic

The time filter logic is shared by both Gaspar and JRC.

The relevant pieces are:

- `PeriodSelection`
- `build_year_period()`
- `build_month_period()`
- `build_single_day_period()`
- `build_custom_range_period()`
- `filter_records_active_between()`

### Important rule

A row is considered active when the row interval overlaps the selected period.

The test is:

- `row_start <= selected_period_end`
- `row_end >= selected_period_start`

This means the app is using **interval overlap**, not exact equality.

Examples:

- if a flood starts on `2021-07-30` and ends on `2021-08-02`, it is active in `2021-07`
- if a flood starts on `2021-06-29` and ends on `2021-07-01`, it is active in `2021-07`
- if a flood ends on `2021-06-30`, it is not active in `2021-07`

This is the correct behavior for month and year browsing.

## 12. Aggregation Logic

After filtering, the app no longer wants raw event rows.

It wants one row per commune.

### Gaspar aggregation

Function:

- `aggregate_gaspar_activity()`

This groups by current `insee_com` and computes fields such as:

- `gaspar_row_count`
- `gaspar_unique_event_count`
- `gaspar_unique_decree_count`
- `gaspar_risk_labels`
- `gaspar_match_methods`

### JRC aggregation

Function:

- `aggregate_jrc_activity()`

This groups by current `insee_com` and computes fields such as:

- `jrc_row_count`
- `jrc_unique_event_count`
- `jrc_max_depth_cm`
- `jrc_total_flooded_area_m2`

So:

- Gaspar aggregation is administrative
- JRC aggregation is flood-footprint oriented

## 13. Comparison Mode

Comparison mode uses:

- `build_comparison_activity()`

This merges the commune-level Gaspar aggregate with the commune-level JRC aggregate.

Then it assigns one of these classes:

- `both`
- `gaspar_only`
- `jrc_only`
- `inactive`

The app later keeps only:

- `both`
- `gaspar_only`
- `jrc_only`

So the comparison map is not a numeric choropleth.

It is a **status map** showing whether a commune is active in Gaspar, JRC, or both.

## 14. Geometry Loading

The app draws current communes from AdminExpress, not from LAU polygons.

Relevant functions:

- `load_commune_geometries()`
- `build_department_boundaries()`
- `build_france_outline()`

### Why AdminExpress

Because the final display target is:

- current French communes

That matches the Gaspar and JRC commune harmonization layer better than showing raw LAU shapes directly.

### Extra map layers

The app optionally adds:

- department boundaries
- France outline

These are separate layers from the commune fill layer.

## 15. Streamlit Caching

The app caches expensive steps heavily.

Important cached functions in `src/gaspar_jrc_france_map_app.py`:

- `cached_load_lookup()`
- `cached_load_history()`
- `cached_prepare_processed_gaspar()`
- `cached_prepare_raw_gaspar()`
- `cached_prepare_jrc()`
- `cached_map_layers()`

Why this matters:

- Gaspar matching can be expensive
- loading commune geometry can be expensive
- you do not want to redo that work every time a user changes month or map style

So Streamlit caches:

- lookup tables
- processed source rows
- map layers

This is why the first load is heavier and later interactions are faster.

## 16. Sidebar To Backend Mapping

The sidebar is not just UI.

Each major control maps directly to code paths.

### Source controls

- `Gaspar input`
  - processed workbook -> `cached_prepare_processed_gaspar()`
  - raw dataset -> `cached_prepare_raw_gaspar()`

- `Display mode`
  - `Gaspar` -> Gaspar aggregate only
  - `JRC` -> JRC aggregate only
  - `Comparison` -> merged comparison aggregate

### Time controls

- `Specific date` -> `build_single_day_period()`
- `Month` -> `build_month_period()`
- `Year` -> `build_year_period()`
- `Custom range` -> `build_custom_range_period()`

### Map controls

- `Metric` chooses the choropleth column
- `Basemap` changes the Leaflet tile layer
- `Show department boundaries` adds or removes the department overlay
- `Commune simplify tolerance` trades detail for lighter geometry

## 17. Map Rendering Logic

The map builder is:

- `build_map()`

There are two broad rendering families.

### Gaspar or JRC mode

The app:

1. converts the selected metric to numeric
2. builds a `YlOrRd` color scale
3. computes one fill color per commune
4. renders communes as Folium `GeoJson`
5. adds tooltips and a color legend

So Gaspar and JRC modes are standard choropleths.

### Comparison mode

Comparison mode does not use a numeric scale.

Instead it uses fixed colors:

- `both` -> green
- `gaspar_only` -> orange
- `jrc_only` -> blue

This makes the overlap / difference interpretation immediate.

## 18. What The Top Metrics Mean

The top metrics come from the filtered tables after time selection.

Examples:

- `Active communes`
  - number of communes in the aggregated table currently shown

- `Filtered Gaspar rows`
  - all Gaspar rows whose event period overlaps the selected period

- `Matched Gaspar rows`
  - filtered Gaspar rows that were successfully mapped to a current commune

- `Unresolved filtered Gaspar rows`
  - filtered Gaspar rows that could not be mapped to a current commune

- `Filtered JRC rows`
  - all JRC commune-event rows whose event period overlaps the selected period

- `Both / Gaspar only / JRC only`
  - comparison-mode counts after commune aggregation

This is an important distinction:

- row counts are event-table counts
- commune counts are aggregated map counts

So one commune can contribute several filtered rows.

## 19. The Tabs

The four tabs correspond to four levels of interpretation.

### `Map`

Best for:

- spatial interpretation
- overlap / difference view
- quickly seeing which areas are active

### `Aggregated table`

Best for:

- one row per displayed commune
- export
- sorting by counts or intensity

### `Filtered rows`

Best for:

- raw audit
- debugging one decree or event
- checking unresolved rows

### `Diagnostics`

Best for:

- verifying data source paths
- seeing matching diagnostics
- understanding how many rows were resolved or unresolved

## 20. Best Reading Order Inside The Code

If you want to understand the code deeply without jumping around too much, use this order:

1. `main()` in `src/gaspar_jrc_france_map_app.py`
2. `build_period_selector()`
3. `metric_options_for_mode()`
4. `build_map()`
5. `cached_prepare_processed_gaspar()`
6. `cached_prepare_raw_gaspar()`
7. `cached_prepare_jrc()`
8. `resolve_gaspar_current_communes()` in `src/france_commune_activity.py`
9. `prepare_jrc_activity_rows()`
10. `aggregate_gaspar_activity()`
11. `aggregate_jrc_activity()`
12. `build_comparison_activity()`

That order moves from:

- user choices
- to loaded data
- to commune matching
- to final map output

## 21. How To Debug A Strange Commune

If one commune looks wrong, the fastest workflow is:

1. pick the same period in the app
2. go to `Filtered rows`
3. search for the commune name or decree code
4. check:
   - `gaspar_source_cod_commune`
   - `gaspar_commune_name`
   - `insee_com`
   - `gaspar_commune_match_method`
   - `gaspar_commune_match_found`
5. if needed, inspect:
   - `fr_lau_insee_lookup.csv`
   - `fr_old_insee_to_current_update_ready.csv`

That tells you whether the issue is:

- source data
- old commune history
- ambiguous name fallback
- current commune reconciliation

## 22. How To Change The Behavior

Here are the most likely edits you may want later.

### Change which raw Gaspar risks are included

Edit:

- `DEFAULT_GASPAR_FLOOD_RISK_LABELS`

### Change how unresolved Gaspar rows are handled

Edit:

- `resolve_gaspar_current_communes()`

### Change the time-overlap definition

Edit:

- `filter_records_active_between()`

### Change the comparison colors

Edit:

- `COMPARISON_COLORS` in `src/gaspar_jrc_france_map_app.py`

### Change what each metric dropdown shows

Edit:

- `metric_options_for_mode()`

### Change what appears in the tooltip

Edit:

- `prepare_tooltip_columns()`
- `build_tooltip_config()`

### Change geometry simplification defaults

Edit:

- the slider defaults in `main()`
- the simplify logic in `cached_map_layers()`

## 23. Important Design Choices

There are a few design decisions worth remembering.

### Design choice 1. Be conservative with commune history

The app does not aggressively guess commune updates.

That avoids false map placements.

### Design choice 2. Use current communes for display

Even though some inputs pass through LAU or old commune codes, the final display target is the current commune map.

### Design choice 3. Filter by interval overlap

This makes month and year browsing meaningful.

### Design choice 4. Separate data preparation from UI rendering

This is why the codebase is reasonably maintainable:

- one file prepares data
- one file presents data

## 24. Quick Mental Model To Keep

If you only remember one thing, remember this:

```text
Gaspar/JRC row
-> normalize dates
-> reconcile to current commune
-> filter by chosen period
-> aggregate by commune
-> join commune geometry
-> render map
```

That is the full app in one line.

## 25. Suggested Next Improvements

If you later want to extend the app, the most natural next additions are:

- explicit `Unresolved Gaspar rows` tab
- optional export of unresolved rows only
- commune search box
- department-level summary cards
- side-by-side Gaspar and JRC maps
- stronger diagnostics for historical commune edge cases

## 26. Final Summary

The France commune activity app is built around a simple architecture:

- read source tables
- map everything possible to current communes
- filter by overlapping period
- aggregate at commune level
- render the result on AdminExpress commune polygons

The hardest and most important part is not the map.

It is the **commune reconciliation logic**, especially for:

- old INSEE codes
- merged communes
- renamed communes
- alphanumeric codes such as Corsica

So if you want to understand the app fully, spend most of your attention on:

- `resolve_gaspar_current_communes()`

That function explains most of the app's intelligence.
