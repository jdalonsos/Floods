# Deep Guide: How `build_flood_lgd_exports.py` Works

This document explains the logic of [src/build_flood_lgd_exports.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports.py) in detail.

It is the **consolidation** step of the T20 flood workflow.

The same consolidation core is also reused by these preset wrappers:

- [src/build_flood_lgd_exports_italy.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_italy.py)
  - Italy T20 preset
  - uses only `JRC` plus `HANZE`, so the effective retained-source priority becomes `JRC > HANZE`
- [src/build_flood_lgd_exports_collaterals.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_collaterals.py)
  - France collaterals preset
- [src/build_flood_lgd_exports_collaterals_italy.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_collaterals_italy.py)
  - Italy collaterals preset
  - uses only `JRC` plus `HANZE`, so the effective retained-source priority becomes `JRC > HANZE`

It assumes that the upstream source-check step has already been run with:

- [src/check_points_against_jrc_floods.py](D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods.py)

That upstream script prepares three checked source workbooks:

- `JRC`
- `GASPAR`
- `HANZE`

This script then merges those three checked sources into one final `FLOOD_LGD` output.

If you only need the high-level split between the source-check step and the consolidation step, see:

- [docs/t20_flood_pipeline_guide.md](D:/M2_MoSEF/DataCollection/docs/t20_flood_pipeline_guide.md)

## 1. Purpose

The purpose of `build_flood_lgd_exports.py` is:

1. read the original source workbook again
2. recover business metadata such as:
   - `point_id`
   - `Obligor_ID`
   - `Facility_ID`
   - `CLOSED_DEFAULT_DATE`
   - `Default_Date`
   - `ID_ADR`
   - `TYPE_ADR`
3. read the checked flood evidence from:
   - JRC
   - GASPAR
   - HANZE
4. standardize those three sources into one common internal event table
5. merge nearby events into consolidated flood episodes using a `30-day` rule
6. write one final output table with the target `FLOOD_LGD` columns

So this script is not a raster script and not a spatial-join script.

It is a **table consolidation and prioritization script**.

## 2. What The Script Produces

The script produces one final table with these columns:

- `point_id`
- `Obligor_ID`
- `Facility_ID`
- `CLOSED_DEFAULT_DATE`
- `Default_Date`
- `ID_ADR`
- `TYPE_ADR`
- `Flag_JRC`
- `Flag_GASPAR`
- `Flag_HANZE`
- `FLOOD_DATA_SOURCE`
- `Flag_JRC_AREA`
- `Flag_GASPAR_AREA`
- `Flag_HANZE_AREA`
- `FLOOD_DATA_SOURCE_AREA`
- `FLAG_FLOOD_ADR`
- `FLAG_FLOOD_ADR_AREA`
- `DATE_REF_FLOOD`
- `DATE_END_FLOOD`
- `FLOOD_DEPTH_MOY`
- `FLOOD_DEPTH_MOY_AREA`
- `FLOOD_DEPTH_MAX`
- `FLOOD_DEPTH_MAX_AREA`

It can write that table in three modes:

- `copy`
  - copy the original source workbook and append a `FLOOD_LGD` sheet
- `standalone`
  - create a small Excel workbook containing only `FLOOD_LGD`
- `csv`
  - create only a semicolon-separated CSV file

For large outputs, `csv` is the safest mode.

The CSV export intentionally uses `;` instead of `,`.

That matters because:

- `ID_ADR` is built from latitude and longitude text
- so one cell often looks like `41.09775000, 16.77685000`
- with a comma-separated CSV, pandas would need to wrap that cell in double quotes
- with a semicolon-separated CSV, the `ID_ADR` cell can stay unquoted

## 3. Granularity

This is the most important concept.

The final output is **not**:

- one row per input workbook row
- one row per source
- one row per raw flood event
- one row per point

It is:

- **one row per `point_id x consolidated flood episode`**

That means:

- one point can appear several times in the final output
- if that point has several separate flood episodes

It also means:

- one final row may combine evidence coming from multiple sources
- if those source events are close enough in time to be treated as one same flood episode

## 4. What The Script Needs

Main inputs:

- original source workbook
  - default: `data/processed/T20_Anonymised.xlsx`
- JRC checked workbook
  - default: `data/processed/T20_Anonymised_jrc_flood_check.xlsx`
- GASPAR checked workbook
  - default: `data/processed/T20_Anonymised_gaspar_check.xlsx`
- HANZE checked workbook
  - default: `data/processed/T20_Anonymised_hanze_check.xlsx`

Italy T20 wrapper defaults:

- original source workbook
  - default: `data/processed/T20_Anonymised.xlsx`
- JRC checked workbook
  - default: `data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx`
- HANZE checked workbook
  - default: `data/processed/T20_Anonymised_italy_hanze_tri_check.xlsx`
- GASPAR
  - not used in the Italy T20 wrapper

Expected sheets:

- JRC workbook:
  - `event_hits`
- GASPAR workbook:
  - `candidate_events`
  - `event_hits`
- HANZE workbook:
  - `candidate_events`
  - `event_hits`

The reason the script reads both `candidate_events` and `event_hits` for GASPAR and HANZE is that:

- `candidate_events` define area-level evidence
- `event_hits` define point-level positive evidence

JRC works differently:

- JRC already stores the necessary point and area flood flags directly in `event_hits`

## 5. High-Level Flow

The execution path inside `main()` is:

1. Parse CLI arguments.
2. Load the original source workbook again.
3. Load JRC `event_hits`.
4. Load GASPAR `candidate_events` and `event_hits`.
5. Load HANZE `candidate_events` and `event_hits`.
6. Standardize all source rows into one common internal event table.
7. Group rows by `point_id`.
8. Within each point, merge nearby events into consolidated clusters using the `30-day` rule.
9. Aggregate each cluster into one final output row.
10. Add one zero row for any point with no flood evidence.
11. Sort the final result.
12. Write the output as Excel or CSV.

## 6. Source Workbook Loading

Function:

- `load_source_frame()`

The script reopens the original source workbook because the checked JRC/GASPAR/HANZE workbooks are not enough by themselves to rebuild all the business metadata needed in the final table.

It normalizes the source workbook in the following way:

1. drop completely empty rows
2. trim column names
3. resolve a point identifier column using this preference order:
   - `point_id`
   - `Point ID`
   - `#`
   - `id`
4. if no point identifier exists, create `point_id = 1..N`
5. resolve latitude and longitude using aliases
6. resolve `CLOSED_DEFAULT_DATE` if present
7. resolve `Default_Date` if present
8. resolve `TYPE_ADR` if present
9. build `ID_ADR` from latitude/longitude text
10. create `point_order = 0..N-1`

Important detail:

- `point_order` is only used later to restore a stable final ordering close to the original workbook order
- `ID_geoloc` is no longer auto-detected as a point identifier in the shared
  exporter core
- that change is intentional because collateral business keys can repeat or be
  empty, while the final flood workflow needs one unique row-level `point_id`

## 7. Date Parsing

Function:

- `parse_date()`

The script accepts several date styles:

- Python `datetime`
- pandas `Timestamp`
- numeric Excel serial dates
- strings

Excel serial dates are converted using:

- base date `1899-12-30`

This matters because source workbooks often mix real date cells and string-looking dates.

## 8. How The Three Sources Are Standardized

Internally, the script tries to force JRC, GASPAR, and HANZE into one common structure.

The standardized internal columns are:

- `point_id`
- `source_label`
- `source_priority`
- `source_event_uid`
- `event_start_date`
- `event_end_date`
- `Flag_JRC`
- `Flag_GASPAR`
- `Flag_HANZE`
- `Flag_JRC_AREA`
- `Flag_GASPAR_AREA`
- `Flag_HANZE_AREA`
- `point_source_active`
- `area_source_active`
- `jrc_point_depth_mean`
- `jrc_area_depth_mean`
- `jrc_point_depth_max`
- `jrc_area_depth_max`

That standardization is what makes a common clustering step possible.

### 8.1 JRC Standardization

Function:

- `build_jrc_event_frame()`

Input:

- JRC `event_hits`

Logic:

1. standardize JRC `start_date` / `end_date`
2. normalize `point_id`
3. compute point-level flood flag:
   - `Flag_JRC = 1` when `point_buffer_flood_hit` is true
4. compute area-level flood flag:
   - `Flag_JRC_AREA = 1` when either:
     - `surrounding_buffer_flood_hit`
     - or `buffer_flood_hit`
5. discard JRC rows where both point and area are zero
6. keep JRC depth fields:
   - point mean depth
   - point max depth
   - area mean depth
   - area max depth

So JRC is the only source that brings depth measurements into the final export.

### 8.2 GASPAR Standardization

Function:

- `build_fallback_event_frame(... source_label="GASPAR" ...)`

Inputs:

- GASPAR `candidate_events`
- GASPAR `event_hits`

Logic:

1. keep only candidate rows that have a `gaspar_event_uid`
2. normalize `point_id`
3. normalize event UID text
4. standardize event start/end dates
5. build a lookup set from GASPAR `event_hits`
6. for each candidate row:
   - if `(point_id, gaspar_event_uid)` is present in `event_hits`
     - `Flag_GASPAR = 1`
   - otherwise
     - `Flag_GASPAR = 0`
7. every surviving candidate row is area-positive:
   - `Flag_GASPAR_AREA = 1`
8. GASPAR gets no depth values:
   - JRC depth fields stay `NaN`

So GASPAR means:

- candidate row = area evidence
- hit row = point evidence

### 8.3 HANZE Standardization

Function:

- `build_fallback_event_frame(... source_label="HANZE" ...)`

Inputs:

- HANZE `candidate_events`
- HANZE `event_hits`

Logic is the same pattern as GASPAR:

1. keep only candidate rows with `hanze_event_uid`
2. standardize dates
3. normalize `point_id`
4. normalize event UID text
5. compare candidate rows against `event_hits`
6. if `(point_id, hanze_event_uid)` is present in `event_hits`
   - `Flag_HANZE = 1`
7. otherwise
   - `Flag_HANZE = 0`
8. all candidate rows are area-positive:
   - `Flag_HANZE_AREA = 1`
9. no depth values are attached

## 9. What `point_source_active` And `area_source_active` Mean

These two internal booleans are subtle but important.

For a standardized event row:

- `point_source_active = True`
  - when that source row is point-positive
- `area_source_active = True`
  - when that source row is area-positive

Examples:

JRC point hit and area hit:

- `point_source_active = True`
- `area_source_active = True`

GASPAR candidate row that did not survive point-hit logic:

- `point_source_active = False`
- `area_source_active = True`

These booleans matter later when the script chooses which rows to use for retained dates.

## 10. Source Priority

The script defines one fixed priority:

1. `JRC`
2. `GASPAR`
3. `HANZE`

This priority is used only **after** cluster formation to decide:

- `FLOOD_DATA_SOURCE`
- `FLOOD_DATA_SOURCE_AREA`

It does **not** decide whether events merge into the same cluster.

That is one of the easiest points to misunderstand.

## 11. The 30-Day Clustering Rule

Function:

- `cluster_point_events()`

This is the central merging rule.

The script works one `point_id` at a time.

For each point:

1. sort all source rows by:
   - `event_start_date`
   - `event_end_date`
   - `source_priority`
   - `source_label`
   - `source_event_uid`
2. start cluster `1` with the first event
3. keep track of:
   - `current_cluster_id`
   - `current_cluster_end`
4. for each next event, compare:
   - `next event start`
   - against `current_cluster_end`

The actual rule is:

- if `next_event_start - current_cluster_end <= merge_gap_days`
  - keep the same cluster
- else
  - create a new cluster

By default:

- `merge_gap_days = 30`

### 11.1 What This Means In Practice

Events are merged when:

- they overlap
- or they start on the same day
- or they start up to 30 days after the current cluster ends

Events split when:

- the next one starts more than 30 days after the current cluster ends

### 11.2 Why This Is A Rolling Rule

The script does not compare only two sources once.

It does rolling clustering.

So if:

- event A is within 30 days of event B
- event B is within 30 days of event C

then all three merge into one cluster

even if event A and event C are more than 30 days apart.

This is the chain-merging effect.

### 11.3 Worked Example

Suppose one point has:

- GASPAR: `2020-01-01` to `2020-01-05`
- JRC: `2020-01-20` to `2020-01-22`
- HANZE: `2020-02-10` to `2020-02-12`

Step 1:

- cluster 1 starts with GASPAR
- current cluster end = `2020-01-05`

Step 2:

- JRC starts on `2020-01-20`
- gap to cluster end = 15 days
- 15 <= 30
- JRC joins cluster 1
- cluster end becomes `2020-01-22`

Step 3:

- HANZE starts on `2020-02-10`
- gap to cluster end = 19 days
- 19 <= 30
- HANZE joins cluster 1

Final result:

- all 3 rows are in the same consolidated flood episode

### 11.4 What The Rule Does Not Do

It does not explicitly check:

- start-to-start distance
- end-to-end distance
- source names
- a custom match table between JRC and GASPAR

It is simply a rolling interval-gap rule within each `point_id`.

## 12. Cluster Aggregation

Function:

- `aggregate_cluster_rows()`

Once a cluster is formed, the script collapses all the rows in that cluster into one final output row.

This happens in several steps.

### 12.1 Source Flags

For each source, the final cluster-level flags are just the max over all rows in the cluster:

- `Flag_JRC`
- `Flag_GASPAR`
- `Flag_HANZE`
- `Flag_JRC_AREA`
- `Flag_GASPAR_AREA`
- `Flag_HANZE_AREA`

So one final row can say:

- `Flag_JRC = 1`
- `Flag_GASPAR = 1`
- `Flag_HANZE = 1`

at the same time.

That means:

- all three sources contributed evidence to the same consolidated flood episode

### 12.2 Consolidated Flood Flags

The script then builds:

- `FLAG_FLOOD_ADR`
- `FLAG_FLOOD_ADR_AREA`

Rules:

- `FLAG_FLOOD_ADR = 1`
  - if any point-level source flag is 1
- `FLAG_FLOOD_ADR_AREA = 1`
  - if any area-level source flag is 1

Equivalent formulas:

- `FLAG_FLOOD_ADR = 1` if `Flag_JRC + Flag_GASPAR + Flag_HANZE > 0`
- `FLAG_FLOOD_ADR_AREA = 1` if `Flag_JRC_AREA + Flag_GASPAR_AREA + Flag_HANZE_AREA > 0`

## 13. How The Retained Source Is Chosen

Function:

- `choose_priority_source()`

This is where source priority matters.

Point-level retained source:

- if `Flag_JRC = 1`
  - `FLOOD_DATA_SOURCE = JRC`
- else if `Flag_GASPAR = 1`
  - `FLOOD_DATA_SOURCE = GASPAR`
- else if `Flag_HANZE = 1`
  - `FLOOD_DATA_SOURCE = HANZE`
- else
  - `FLOOD_DATA_SOURCE = NA`

Area-level retained source:

- if `Flag_JRC_AREA = 1`
  - `FLOOD_DATA_SOURCE_AREA = JRC`
- else if `Flag_GASPAR_AREA = 1`
  - `FLOOD_DATA_SOURCE_AREA = GASPAR`
- else if `Flag_HANZE_AREA = 1`
  - `FLOOD_DATA_SOURCE_AREA = HANZE`
- else
  - `FLOOD_DATA_SOURCE_AREA = NA`

This means:

- point and area can retain different source names

Example:

- `FLOOD_DATA_SOURCE = GASPAR`
- `FLOOD_DATA_SOURCE_AREA = JRC`

is a valid outcome.

## 14. How Final Dates Are Chosen

This is one of the most subtle behaviors in the script.

The final dates are **not** currently:

- earliest start across the whole merged cluster
- latest end across the whole merged cluster

Instead:

1. if a point-level retained source exists:
   - use rows from that retained point source
2. otherwise, if only an area-level retained source exists:
   - use rows from that retained area source

Then:

- `DATE_REF_FLOOD = min(selected_source_rows.event_start_date)`
- `DATE_END_FLOOD = max(selected_source_rows.event_end_date)`

So the date range shown in the final row comes from the retained source, not necessarily from the whole merged cluster.

### 14.1 Example

Suppose one merged cluster contains:

- GASPAR: `2020-01-01` to `2020-01-05`
- JRC: `2020-01-20` to `2020-01-22`
- HANZE: `2020-02-10` to `2020-02-12`

If all three are point-positive:

- `FLOOD_DATA_SOURCE = JRC`

Then final dates become:

- `DATE_REF_FLOOD = 2020-01-20`
- `DATE_END_FLOOD = 2020-01-22`

not:

- `2020-01-01`
- `2020-02-12`

So:

- clustering uses all source dates
- final retained dates use only the retained source rows

## 15. JRC Depth Behavior

JRC is the only source that can fill:

- `FLOOD_DEPTH_MOY`
- `FLOOD_DEPTH_MOY_AREA`
- `FLOOD_DEPTH_MAX`
- `FLOOD_DEPTH_MAX_AREA`

Rules:

- point depth fields are only filled when retained point source is `JRC`
- area depth fields are only filled when retained area source is `JRC`
- otherwise those depth columns stay `NA`

The script currently uses the maximum depth among the relevant JRC rows in the cluster.

## 16. Zero-Flood Rows

If a point has no consolidated flood cluster at all, the script still outputs one row for that point.

That row gets:

- source-specific flags = `0`
- `FLAG_FLOOD_ADR = 0`
- `FLAG_FLOOD_ADR_AREA = 0`
- `FLOOD_DATA_SOURCE = NA`
- `FLOOD_DATA_SOURCE_AREA = NA`
- `DATE_REF_FLOOD = NA`
- `DATE_END_FLOOD = NA`
- depth columns = `NA`

This behavior ensures the final output still preserves points that had no flood evidence.

## 17. Final Ordering

After all rows are built, the script sorts using:

1. `point_order`
2. `DATE_REF_FLOOD`

That means:

- rows stay close to original source workbook order
- and within one point they are ordered by retained flood start date

## 18. Output Writing

### 18.1 Excel Copy Mode

Function:

- `write_sheet_into_existing_workbook()`

Behavior:

- open original workbook
- optionally replace existing sheet
- append `FLOOD_LGD`
- apply simple styling

### 18.2 Standalone Excel Mode

Function:

- `write_standalone_workbook()`

Behavior:

- create a fresh workbook
- write `FLOOD_LGD`
- style the sheet

### 18.3 CSV Mode

Function:

- `write_csv_output()`

Behavior:

- write the final dataframe in CSV chunks
- print progress after each chunk

Defaults:

- `csv_chunk_size = 200000`

## 19. Progress Logging

The script now includes progress logging via:

- `log_progress()`

By default it prints:

- loading steps
- normalization steps
- clustering progress
- aggregation progress
- CSV chunk-writing progress

Defaults:

- `progress_every_points = 5000`
- `csv_chunk_size = 200000`

Useful CLI flags:

- `--progress-every-points`
- `--csv-chunk-size`
- `--quiet`

## 20. Performance Notes

This script can be slow on very large datasets for structural reasons:

1. it reads several Excel workbooks
2. it normalizes several large tables in pandas
3. clustering is done point by point
4. cluster aggregation is done cluster by cluster
5. the final output can become much larger than the original point workbook because one point can generate multiple consolidated flood rows

When the dataset is large:

- prefer `--mode csv`
- keep progress logging enabled

## 21. Excel Row-Limit Caveat

The script does **not** currently split Excel output across multiple sheets when the result exceeds Excel's sheet limit.

Important Excel limit:

- maximum rows per worksheet: `1,048,576`

So:

- `copy` mode is not safe for very large outputs
- `standalone` mode is not safe for very large outputs
- `csv` mode is the recommended choice when the output may exceed that size

## 22. Missing HANZE Workbook Behavior

If the HANZE workbook does not exist:

- the script does not crash immediately
- it prints a message
- HANZE columns stay zero or `NA`

That allows the exporter to still run in a partially available setup.

## 23. Recommended Commands

### 23.1 Standard T20 CSV Run

```bash
./.venv/Scripts/python.exe src/build_flood_lgd_exports.py \
  --source-workbook "data/processed/T20_Anonymised.xlsx" \
  --jrc-workbook "data/processed/T20_Anonymised_jrc_flood_check.xlsx" \
  --gaspar-workbook "data/processed/T20_Anonymised_gaspar_check.xlsx" \
  --hanze-workbook "data/processed/T20_Anonymised_hanze_check.xlsx" \
  --output-dir outputs/flood_lgd_export \
  --sheet-name FLOOD_LGD \
  --merge-gap-days 30 \
  --mode csv
```

### 23.2 More Frequent Progress Updates

```bash
./.venv/Scripts/python.exe src/build_flood_lgd_exports.py \
  --source-workbook "data/processed/T20_Anonymised.xlsx" \
  --jrc-workbook "data/processed/T20_Anonymised_jrc_flood_check.xlsx" \
  --gaspar-workbook "data/processed/T20_Anonymised_gaspar_check.xlsx" \
  --hanze-workbook "data/processed/T20_Anonymised_hanze_check.xlsx" \
  --output-dir outputs/flood_lgd_export \
  --sheet-name FLOOD_LGD \
  --merge-gap-days 30 \
  --mode csv \
  --progress-every-points 1000 \
  --csv-chunk-size 100000
```

### 23.3 France Collaterals CSV Run

```bash
./.venv/Scripts/python.exe src/build_flood_lgd_exports_collaterals.py \
  --source-workbook data/raw/my_collaterals_points.xlsx \
  --mode csv
```

This wrapper reuses the same consolidation logic, but its source defaults are:

- `source_point_id_col = None`
  - the exporter creates a sequential row-level `point_id`
- `source_latitude_col = lat`
- `source_longitude_col = lon`
- `source_closed_default_col = Closed_Default_Date`
- `source_closed_default_fallback_col = None`
- `CLOSED_DEFAULT_DATE` stays empty when `Closed_Default_Date` is empty
- `source_default_date_col = Default_Date`
- `source_obligor_id_col = Obligor_ID`
- `source_facility_id_col = Facility_ID`
- `source_type_adr_value = Collateral`

### 23.4 Italy T20 CSV Run

```bash
./.venv/Scripts/python.exe src/build_flood_lgd_exports_italy.py \
  --source-workbook data/processed/T20_Anonymised.xlsx \
  --jrc-workbook data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx \
  --hanze-workbook data/processed/T20_Anonymised_italy_hanze_tri_check.xlsx \
  --output-dir outputs/flood_lgd_export \
  --sheet-name FLOOD_LGD \
  --merge-gap-days 30 \
  --mode csv
```

This wrapper reuses the same `30-day` consolidation rule, but it differs from the France T20 exporter in two important ways:

- it loads only `JRC` plus `HANZE`
- it expects the Italy checker output family `*_italy_jrc_flood_check.xlsx` and `*_italy_hanze_tri_check.xlsx`

Its source defaults are:

- `source_point_id_col = #`
- `source_latitude_col = LAT`
- `source_longitude_col = LONG`
- `source_closed_default_col = Closed_Default_Date`
- `source_default_date_col = Default_Date`
- `source_obligor_id_col = Obligor_ID`
- `source_facility_id_col = Facility_ID`
- `source_type_adr_col = TYPE_ADR`

### 23.5 Italy Collaterals CSV Run

```bash
./.venv/Scripts/python.exe src/build_flood_lgd_exports_collaterals_italy.py \
  --source-workbook data/raw/my_italy_collaterals_points.xlsx \
  --mode csv
```

This wrapper also reuses the same `30-day` consolidation rule, but it differs in two important ways:

- it loads only `JRC` plus `HANZE`
- it writes semicolon-separated CSV output in the same way as the main exporter

Its source defaults are:

- `source_point_id_col = None`
  - a sequential `point_id` is created per workbook row
- `source_latitude_col = lat`
- `source_longitude_col = lon`
- `source_closed_default_col = Closed_Default_Date`
- `source_closed_default_fallback_col = None`
- `CLOSED_DEFAULT_DATE` stays empty when `Closed_Default_Date` is empty
- `source_default_date_col = Default_Date`
- `source_facility_id_col = KEY_COLLATERAL`
- `source_type_adr_value = Collateral`

### 23.6 Fast Default_Date Backfill On An Existing FLOOD_LGD File

If you already built the final FLOOD_LGD output and only forgot to carry `Default_Date`
from the original T20 workbook, you do **not** need to rerun the expensive flood
clustering step.

Use:

```bash
./.venv/Scripts/python.exe src/add_default_date_to_flood_lgd.py \
  --source-workbook data/processed/T20_Anonymised.xlsx \
  --flood-lgd-file outputs/flood_lgd_export/T20_Anonymised_FLOOD_LGD.csv
```

That helper:

- reloads only the original source workbook
- matches `point_id`
- adds or refreshes the `Default_Date` column
- writes a sibling file with a `_with_default_date` suffix by default

If you want to overwrite the existing file in place, add:

```bash
  --in-place
```

For current France collaterals, the same helper works with the generated
row-level `point_id`, so you should omit `--source-point-id-col`:

```bash
./.venv/Scripts/python.exe src/add_default_date_to_flood_lgd.py \
  --source-workbook data/raw/my_collaterals_points.xlsx \
  --flood-lgd-file outputs/flood_lgd_export/my_collaterals_points_FLOOD_LGD.csv \
  --source-default-date-col Default_Date
```

If you are patching an older France-collateral export created before the
row-level `point_id` fix, that older file may still require:

```bash
  --source-point-id-col ID_geoloc
```

For Italy collaterals, keep the same helper and omit `--source-point-id-col`
when the export used the sequential row-based `point_id` generated by the
pipeline:

```bash
./.venv/Scripts/python.exe src/add_default_date_to_flood_lgd.py \
  --source-workbook data/raw/my_italy_collaterals_points.xlsx \
  --flood-lgd-file outputs/flood_lgd_export/my_italy_collaterals_points_FLOOD_LGD.csv \
  --source-default-date-col Default_Date
```

### 23.7 Fast NUTS 1/2/3 Enrichment On An Existing FLOOD_LGD File

If the final FLOOD_LGD file is already built and you only need regional
metadata for mapping, you do **not** need to rerun the France flood check or
the final cross-source consolidation.

Use:

```bash
./.venv/Scripts/python.exe src/add_nuts_to_flood_lgd.py \
  --flood-lgd-file outputs/flood_lgd_export_csv/T20_Anonymised_jrc_flood_check_FLOOD_LGD.csv \
  --nuts-file NUTS_RG_03M_2024_4326.gpkg
```

That helper:

- reads the existing FLOOD_LGD CSV or XLSX
- parses `ID_ADR`
- builds point geometries in `EPSG:4326`
- loads the official Eurostat NUTS GeoPackage
- filters it to the requested country code
- spatially joins the point to NUTS levels `1`, `2`, and `3`
- writes a sibling file with a `_with_nuts` suffix by default

For France, the default assumptions are:

- `--id-adr-col ID_ADR`
- `--country-code FR`
- `--nuts-file NUTS_RG_03M_2024_4326.gpkg`

The output adds:

- `point_latitude`
- `point_longitude`
- `id_adr_coordinate_order`
- `id_adr_order_resolution`
- `nuts1_code`
- `nuts1_name`
- `nuts2_code`
- `nuts2_name`
- `nuts3_code`
- `nuts3_name`

The matching source files are:

- the existing FLOOD_LGD export you pass in `--flood-lgd-file`
- the official NUTS GeoPackage passed in `--nuts-file`

The helper is conservative about coordinates:

- it expects `ID_ADR` to contain two coordinates in one text cell
- it defaults to `lat, lon`
- it can still test both `lat, lon` and `lon, lat` if needed
- it keeps the detected order and resolution path in the diagnostic columns

CSV delimiter behavior:

- newly built standalone `csv` exports still target `;`
- some older or already-saved FLOOD_LGD CSV files can still be comma-delimited
- this helper auto-detects `;` or `,` from the input file
- it preserves the detected delimiter when writing the enriched output

## 24. Worked End-To-End Example

Suppose one point has these source rows after standardization:

1. GASPAR
   - start = `2020-01-01`
   - end = `2020-01-05`
   - `Flag_GASPAR = 1`
   - `Flag_GASPAR_AREA = 1`

2. JRC
   - start = `2020-01-20`
   - end = `2020-01-22`
   - `Flag_JRC = 1`
   - `Flag_JRC_AREA = 1`

3. HANZE
   - start = `2020-02-10`
   - end = `2020-02-12`
   - `Flag_HANZE = 1`
   - `Flag_HANZE_AREA = 1`

Clustering:

- GASPAR opens cluster 1
- JRC joins cluster 1 because gap is 15 days
- HANZE joins cluster 1 because gap is 19 days from the updated cluster end

Cluster-level flags:

- `Flag_JRC = 1`
- `Flag_GASPAR = 1`
- `Flag_HANZE = 1`
- `Flag_JRC_AREA = 1`
- `Flag_GASPAR_AREA = 1`
- `Flag_HANZE_AREA = 1`
- `FLAG_FLOOD_ADR = 1`
- `FLAG_FLOOD_ADR_AREA = 1`

Retained sources:

- `FLOOD_DATA_SOURCE = JRC`
- `FLOOD_DATA_SOURCE_AREA = JRC`

Final dates:

- `DATE_REF_FLOOD = 2020-01-20`
- `DATE_END_FLOOD = 2020-01-22`

Final depth fields:

- filled from JRC because JRC is the retained source

So the final row means:

- this consolidated flood episode is supported by all three sources
- but the retained source label and dates are JRC because JRC has highest priority

## 25. The Most Important Mental Model

This script does two separate things:

### 25.1 Merging

Question:

- do these source rows belong to the same flood episode?

Answered by:

- the rolling `30-day` gap rule within one `point_id`

### 25.2 Retention

Question:

- which source name and which dates should be written to the final row?

Answered by:

- source priority `JRC > GASPAR > HANZE`

If you remember only one thing, remember this:

- **date clustering decides which rows belong together**
- **source priority decides how the final merged row is labeled**
