# Guide: How `check_italy_points_against_jrc_hanze.py` Works

This document explains the Italy-specific workflow implemented in
`src/check_italy_points_against_jrc_hanze.py`.

It is the companion guide for the Italy version of the point-screening logic.

For the output-column definitions, see:

- `docs/italy_flood_workbook_column_dictionary.md`

## 1. Purpose

The Italy workflow produces two separate point-level flood-screening outputs.

1. JRC workbook:
   uses the same JRC raster-confirmation logic as the France script.
2. HANZE plus TRI workbook:
   replaces the France Gaspar branch with an Italy-specific rule:
   keep a positive flag only when:
   - the point belongs to a HANZE event through its `NUTS3` region
   - and the point falls inside the Italian high-hazard flood layer
     `HPH ... elevata`

So the two branches answer different questions:

- JRC branch:
  did the Copernicus / JRC raster evidence show flooding near the point?
- HANZE plus TRI branch:
  if we use the Italy fallback logic, does the point both:
  - sit in a NUTS3 area affected by a HANZE flood event
  - and intersect the Italian `elevata` flood-risk geometry?

## 2. Main Differences From The France Script

This script intentionally reuses the France JRC machinery where possible, but
it changes the fallback branch.

Shared with `src/check_points_against_jrc_floods.py`:

- Excel header detection
- latitude / longitude parsing
- row-level study-period logic
- LAU spatial join
- JRC candidate-event filtering
- raster path resolution
- `40 m` local buffer inspection
- `1 km` surrounding buffer inspection
- workbook writing pattern

Italy-specific changes:

- default point file is `data/processed/T20_Anonymised.xlsx`
- default LAU country filter is `IT`
- NUTS enrichment comes from:
  `data/processed/_outputs_eurostat_full/lau_nuts_lookup.csv`
- HANZE fallback events come from:
  `data/processed/HANZE_events_v3_transformed.csv`
- Italian hazard geometry comes from:
  `data/raw/Mosaicatura_ISPRA_2020_aree_pericolosita_idraulica`
- only the high-hazard `HPH ... elevata` layer is used
- there is no Gaspar branch in this Italy script
- there is no riparian fallback in this Italy script

## 3. Default Inputs

Main defaults:

- points workbook:
  `data/processed/T20_Anonymised.xlsx`
- LAU polygons:
  `data/raw/LAU_RG_01M_2024_4326.gpkg`
- LAU to NUTS lookup:
  `data/processed/_outputs_eurostat_full/lau_nuts_lookup.csv`
- processed JRC event table:
  `data/processed/_outputs_eurostat_full/events_lau_long.parquet`
- JRC TIFF root:
  `data/JRC_flood_depth_maps`
- HANZE events:
  `data/processed/HANZE_events_v3_transformed.csv`
- Italian TRI folder:
  `data/raw/Mosaicatura_ISPRA_2020_aree_pericolosita_idraulica`

Default outputs:

- JRC workbook:
  `data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx`
- HANZE plus TRI workbook:
  derived automatically as
  `data/processed/T20_Anonymised_italy_hanze_tri_check.xlsx`

## 4. High-Level Flow

Inside `main()`, the workflow is:

1. Load the point workbook.
2. Optionally derive row-level study windows.
3. Load Italy LAU polygons only.
4. Map the points to LAUs.
5. Attach `nuts0` to `nuts3` metadata from the LAU-NUTS lookup CSV.
6. Run the JRC branch:
   - keep only JRC events touching the mapped LAUs
   - apply the same date logic as the France script
   - inspect the actual TIFFs around each point
   - write the JRC workbook
7. Run the HANZE plus TRI branch:
   - keep only HANZE rows for `Country code = IT`
   - keep only HANZE rows whose `NUTS3` matches one of the point `NUTS3`
   - apply the same row-level date logic
   - classify each point against the Italian `HPH ... elevata` layer
   - flag a row only when both conditions are true
   - write the HANZE plus TRI workbook

## 5. Row-Level Date Logic

The date logic is intentionally the same as in the France point workflow.

If you pass row-level date columns, the script derives:

- `study_period_anchor_date`
- `study_period_primary_end_date`
- `study_period_fallback_end_date`
- `study_period_start`
- `study_period_end`
- `study_period_end_source`

For the T20-style setup, the usual mapping is:

- anchor date:
  `Reference_Date`
- preferred end date:
  `Closed_Default_Date`
- fallback end date:
  `Cut_off_Date`

Without a lookback parameter, the practical rule is:

- keep full history on the left side
- stop at `Closed_Default_Date`
- if that field is empty, stop at `Cut_off_Date`

This same interval logic is applied to:

- JRC event dates:
  `start_date`, `end_date`
- HANZE event dates:
  `hanze_start_date`, `hanze_end_date`

## 6. JRC Branch

The JRC branch is still the stronger spatial test because it checks the actual
flood TIFFs.

The steps are:

1. Match each point to a LAU.
2. Keep only processed JRC events already linked to that LAU.
3. Apply the optional global date filter.
4. Apply the row-level interval.
5. Resolve the raster path for each remaining event.
6. Open only those candidate TIFFs.
7. Measure flood presence in:
   - the `40 m` point buffer
   - the `1 km` surrounding buffer

The JRC workbook stays positive for a point when at least one candidate event
has:

- `point_buffer_flood_hit = True`
- or `surrounding_buffer_flood_hit = True`

## 7. HANZE Plus TRI Branch

This is the Italy-specific replacement for the France Gaspar fallback.

### 7.1 HANZE candidate selection

The script reads the transformed HANZE file where each row already corresponds
to one `event x NUTS3` combination.

It keeps only rows where:

- `Country code = IT`
- `NUTS3` matches one of the point `nuts3_code` values

Then it standardizes:

- `hanze_event_id`
- `hanze_event_uid`
- `hanze_start_date`
- `hanze_end_date`
- `hanze_country_code`
- `hanze_country_name`
- `hanze_event_type`
- `hanze_flood_source`

If one side of the HANZE date interval is missing, the script fills it from the
other side so the event can still behave as a single-date interval.

### 7.2 Italian TRI spatial classification

The script does not use all Italian hazard layers.

It looks only for the high-hazard layer:

- `HPH_Mosaicatura_ISPRA_2020_pericolosita_idraulica_elevata.shp`

The detection is flexible:

- if the root is a folder, it scans for a `.shp` whose filename starts with
  `HPH_` or contains `elevata`
- if the root is a zip archive, it does the same inside the zip

The geometry is read in its native projected CRS and then converted to
`EPSG:4326` for the final point intersection test.

Each point receives:

- `italy_tri_high_hazard_hit`
- `flood_risk_area_value`

Current values are:

- `high`
- `other`

### 7.3 Final HANZE decision rule

The candidate sheet already represents rows where the point has a HANZE match
through its `NUTS3`.

The final spatial rule is therefore:

- if `italy_tri_high_hazard_hit = True` then `hanze_spatial_hit = True`
- otherwise `hanze_spatial_hit = False`

This means the final positive condition is exactly:

- `in_hanze`
- and `inside HPH / elevata`

The helper reason field is:

- `hanze_and_tri_high`
- or `hanze_without_tri_high`

## 8. Output Workbooks

Both output workbooks use the same four-sheet pattern:

- `point_flags`
- `Detailed`
- `candidate_events`
- `event_hits`

Interpretation:

- `point_flags`:
  one row per unique point ID with a `0/1` flag
- `Detailed`:
  the original workbook rows plus the leading `point_id` and `touched` fields
- `candidate_events`:
  all surviving point-event rows after the branch-specific date filters
- `event_hits`:
  only the final positives for that branch

Branch meaning:

- JRC workbook:
  positives are raster-confirmed local or nearby flood hits
- HANZE plus TRI workbook:
  positives are HANZE-matched rows whose points fall inside the high-hazard
  Italian TRI layer

## 9. Example Command

Typical T20-style run:

```bash
python src/check_italy_points_against_jrc_hanze.py \
  --points-file data/processed/T20_Anonymised.xlsx \
  --sheet-name Feuil2 \
  --latitude-col LAT \
  --longitude-col LONG \
  --row-study-anchor-col Reference_Date \
  --row-study-end-col Closed_Default_Date \
  --row-study-end-fallback-col Cut_off_Date \
  --point-buffer-m 40 \
  --buffer-km 1 \
  --out-file data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx
```

That one command writes both output workbooks.

## 10. Important Limitations

The main limitations are:

- HANZE fallback is not point-precise flood evidence:
  it is a `NUTS3` event match combined with a high-hazard polygon test
- if a point fails to map to a LAU, the JRC branch cannot continue normally
- if a point lacks `nuts3_code`, the HANZE branch cannot match it
- the Italian fallback uses only `HPH / elevata`, not medium or low hazard
- JRC can still miss floods when the processed event table or the raster archive
  itself does not capture the local event

Recommended interpretation:

- treat the JRC workbook as the stronger event-specific spatial evidence
- treat the HANZE plus TRI workbook as a structured fallback screening layer for
  Italy
