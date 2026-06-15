# Italy Flood Workbook Column Dictionary

This document explains the output columns written by
`src/check_italy_points_against_jrc_hanze.py`.

Current output files:

- `data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx`
- `data/processed/T20_Anonymised_italy_hanze_tri_check.xlsx`

For the full workflow description, see:

- `docs/check_italy_points_against_jrc_hanze_guide.md`

## 1. Workbook Structure

Both workbooks use the same sheet names:

- `point_flags`
- `Detailed`
- `candidate_events`
- `event_hits`

Meaning:

- `point_flags` gives one row per unique point ID and a simple `0/1` flag.
- `Detailed` keeps the original input rows plus a leading binary `touched`
  field.
- `candidate_events` keeps the branch-specific point-event diagnostics.
- `event_hits` keeps only the positive rows for that branch.

Large-sheet note:

- if a sheet exceeds the Excel row limit, the export helper automatically splits
  it into numbered tabs such as `candidate_events_2`

## 2. Shared `point_flags` Columns

These columns are the same in both workbooks.

| Column | Meaning |
| --- | --- |
| `point_id` | Unique point identifier from the input workbook. |
| `flag_flood` | Final point-level flag. `1` means at least one positive event hit exists for that point in that workbook. `0` means none exists. |

## 3. Shared `Detailed` Sheet

The `Detailed` sheet is also shared in shape across both workbooks.

Rules:

- `point_id` is moved to the front
- `touched` is inserted immediately after it
- all original workbook columns are kept after those leading fields
- any derived study-window columns added before export are also kept

Meaning of `touched`:

- JRC workbook:
  `1` means the point has at least one positive JRC raster hit
- HANZE plus TRI workbook:
  `1` means the point has at least one row that matches both HANZE and the
  Italian high-hazard TRI layer

Common derived date fields when row-level windows are used:

- `study_period_anchor_date`
- `study_period_primary_end_date`
- `study_period_fallback_end_date`
- `study_period_start`
- `study_period_end`
- `study_period_end_source`

## 4. JRC Workbook

### 4.1 JRC `candidate_events`

This sheet contains all point x JRC-event rows that survive:

- the LAU prefilter
- the optional global date filter
- the row-level date filter

Common columns are:

| Column | Meaning |
| --- | --- |
| `point_id` | Unique point identifier. |
| `point_city` | Optional label column from the source workbook when available. |
| `excel_row_number` | Original Excel row number after header detection. |
| `point_latitude` | Point latitude used by the script. |
| `point_longitude` | Point longitude used by the script. |
| `lau_code` | Eurostat LAU code matched to the point. |
| `lau_name` | LAU name matched to the point. |
| `nuts3_code` | NUTS3 code attached to the matched LAU through the lookup CSV. |
| `nuts3_name` | NUTS3 name attached to the matched LAU through the lookup CSV. |
| `study_period_anchor_date` | Optional row-level anchor date copied into the output. |
| `study_period_primary_end_date` | Optional preferred row-level end date. |
| `study_period_fallback_end_date` | Optional fallback row-level end date. |
| `study_period_start` | Effective row-level start date. |
| `study_period_end` | Effective row-level end date. |
| `study_period_end_source` | Which raw source column supplied the effective end date. |
| `event_id` | JRC flood event identifier. |
| `raster_file` | TIFF filename linked to the event. |
| `resolved_raster_path` | Resolved TIFF path used at runtime when found. |
| `start_date` | JRC event start date. |
| `end_date` | JRC event end date. |
| `duration_days` | Event duration in days. |
| `max_depth_cm` | Maximum flood depth for that `event x LAU` row in the processed event table. |
| `flooded_pixels` | Total flooded pixels for that `event x LAU` row in the processed event table. |
| `flooded_area_m2` | Total flooded area for that `event x LAU` row in the processed event table. |
| `raster_path_found` | `True` when the script successfully located the event TIFF. |
| `hit_at_point` | Historical alias of the `40 m` local buffer hit. |
| `exact_point_depth_cm` | Current depth field exported for the local `40 m` branch. |
| `point_buffer_total_pixels` | Number of raster pixels inspected inside the `40 m` local buffer. |
| `point_buffer_flood_hit` | `True` when at least one flooded pixel above threshold exists in the `40 m` local buffer. |
| `point_buffer_flooded_pixels` | Count of flooded pixels inside the `40 m` local buffer. |
| `point_buffer_flooded_pixel_pct` | Share of flooded pixels inside the `40 m` local buffer. |
| `point_buffer_flooded_area_m2` | Flooded area inside the `40 m` local buffer. |
| `point_buffer_min_depth_cm` | Minimum flooded-pixel depth inside the `40 m` local buffer. |
| `point_buffer_max_depth_cm` | Maximum flooded-pixel depth inside the `40 m` local buffer. |
| `point_buffer_median_depth_cm` | Median flooded-pixel depth inside the `40 m` local buffer. |
| `point_buffer_mean_depth_cm` | Mean flooded-pixel depth inside the `40 m` local buffer. |
| `point_buffer_radius_m` | Radius of the local point buffer, in meters. |
| `buffer_total_pixels` | Number of raster pixels inspected inside the `1 km` surrounding buffer. |
| `buffer_flood_hit` | `True` when flooded pixels above threshold exist inside the `1 km` surrounding buffer. |
| `buffer_flooded_pixels` | Count of flooded pixels inside the `1 km` surrounding buffer. |
| `buffer_flooded_pixel_pct` | Share of flooded pixels inside the `1 km` surrounding buffer. |
| `buffer_flooded_area_m2` | Flooded area inside the `1 km` surrounding buffer. |
| `buffer_min_depth_cm` | Minimum flooded-pixel depth inside the `1 km` surrounding buffer. |
| `buffer_max_depth_cm` | Maximum flooded-pixel depth inside the `1 km` surrounding buffer. |
| `buffer_median_depth_cm` | Median flooded-pixel depth inside the `1 km` surrounding buffer. |
| `buffer_mean_depth_cm` | Mean flooded-pixel depth inside the `1 km` surrounding buffer. |
| `buffer_radius_km` | Radius of the surrounding buffer, in kilometers. |
| `surrounding_buffer_total_pixels` | Duplicate descriptive field for the `1 km` surrounding-buffer pixel count. |
| `surrounding_buffer_flood_hit` | Duplicate descriptive field for the `1 km` surrounding-buffer flood hit. |
| `surrounding_buffer_flooded_pixels` | Duplicate descriptive field for flooded pixels in the `1 km` surrounding buffer. |
| `surrounding_buffer_flooded_pixel_pct` | Duplicate descriptive field for the flooded share in the `1 km` surrounding buffer. |
| `surrounding_buffer_flooded_area_m2` | Duplicate descriptive field for flooded area in the `1 km` surrounding buffer. |
| `surrounding_buffer_min_depth_cm` | Duplicate descriptive field for minimum flooded depth in the `1 km` surrounding buffer. |
| `surrounding_buffer_max_depth_cm` | Duplicate descriptive field for maximum flooded depth in the `1 km` surrounding buffer. |
| `surrounding_buffer_median_depth_cm` | Duplicate descriptive field for median flooded depth in the `1 km` surrounding buffer. |
| `surrounding_buffer_mean_depth_cm` | Duplicate descriptive field for mean flooded depth in the `1 km` surrounding buffer. |
| `surrounding_buffer_radius_km` | Duplicate descriptive field for the `1 km` surrounding-buffer radius. |

### 4.2 JRC `event_hits`

This sheet is the positive subset of the JRC `candidate_events` sheet.

A row is kept when:

- `point_buffer_flood_hit = True`
- or `buffer_flood_hit = True`

Core columns are:

| Column | Meaning |
| --- | --- |
| `point_id` | Unique point identifier. |
| `excel_row_number` | Original Excel row number after header detection. |
| `point_latitude` | Point latitude used by the script. |
| `point_longitude` | Point longitude used by the script. |
| `lau_code` | LAU code matched to the point. |
| `lau_name` | LAU name matched to the point. |
| `Reference_Date` | Raw input date column when it exists in the source workbook. |
| `Closed_Default_Date` | Raw preferred row-level end date when it exists in the source workbook. |
| `Cut_off_Date` | Raw fallback row-level end date when it exists in the source workbook. |
| `study_period_end` | Effective row-level end date used for event filtering. |
| `study_period_end_source` | Which source column supplied the effective end date. |
| `event_id` | JRC flood event identifier. |
| `raster_file` | TIFF filename used for the raster inspection. |
| `start_date` | JRC event start date. |
| `end_date` | JRC event end date. |
| `duration_days` | Event duration in days. |
| `max_depth_cm` | Maximum flood depth for that `event x LAU` row in the processed event table. |
| `flooded_pixels` | Flooded pixels for that `event x LAU` row in the processed event table. |
| `flooded_area_m2` | Flooded area for that `event x LAU` row in the processed event table. |
| `hit_at_point` | Historical alias for the `40 m` local hit. |
| `exact_point_depth_cm` | Current depth field exported for the local `40 m` branch. |
| `point_buffer_radius_m` | Local buffer radius in meters. |
| `point_buffer_flood_hit` | `True` when the `40 m` local buffer is positive. |
| `point_buffer_flooded_pixels` | Flooded pixels inside the `40 m` local buffer. |
| `point_buffer_flooded_pixel_pct` | Flooded share inside the `40 m` local buffer. |
| `point_buffer_flooded_area_m2` | Flooded area inside the `40 m` local buffer. |
| `point_buffer_min_depth_cm` | Minimum flooded depth inside the `40 m` local buffer. |
| `point_buffer_max_depth_cm` | Maximum flooded depth inside the `40 m` local buffer. |
| `point_buffer_median_depth_cm` | Median flooded depth inside the `40 m` local buffer. |
| `point_buffer_mean_depth_cm` | Mean flooded depth inside the `40 m` local buffer. |
| `buffer_radius_km` | Surrounding-buffer radius in kilometers. |
| `buffer_flood_hit` | `True` when the `1 km` surrounding buffer is positive. |
| `buffer_flooded_pixels` | Flooded pixels inside the `1 km` surrounding buffer. |
| `buffer_flooded_pixel_pct` | Flooded share inside the `1 km` surrounding buffer. |
| `buffer_flooded_area_m2` | Flooded area inside the `1 km` surrounding buffer. |
| `buffer_min_depth_cm` | Minimum flooded depth inside the `1 km` surrounding buffer. |
| `buffer_max_depth_cm` | Maximum flooded depth inside the `1 km` surrounding buffer. |
| `buffer_median_depth_cm` | Median flooded depth inside the `1 km` surrounding buffer. |
| `buffer_mean_depth_cm` | Mean flooded depth inside the `1 km` surrounding buffer. |

## 5. HANZE Plus TRI Workbook

### 5.1 HANZE `candidate_events`

This sheet contains all point x HANZE-event rows that survive:

- the `Country code = IT` filter
- the `NUTS3` match
- the optional global date filter
- the row-level date filter

Core columns are:

| Column | Meaning |
| --- | --- |
| `point_id` | Unique point identifier. |
| `point_city` | Optional label column from the source workbook when available. |
| `excel_row_number` | Original Excel row number after header detection. |
| `point_latitude` | Point latitude used by the script. |
| `point_longitude` | Point longitude used by the script. |
| `lau_code` | LAU code matched to the point. |
| `lau_name` | LAU name matched to the point. |
| `nuts3_code` | NUTS3 code attached to the matched LAU. This is the key used for the HANZE match. |
| `nuts3_name` | NUTS3 name attached to the matched LAU. |
| `hanze_event_uid` | Unique row identifier built by the script for each `HANZE event x NUTS3` match. |
| `hanze_event_id` | Original HANZE event ID. |
| `hanze_start_date` | Standardized HANZE event start date. |
| `hanze_end_date` | Standardized HANZE event end date. |
| `hanze_country_code` | HANZE country code, expected to be `IT` in this workflow. |
| `hanze_country_name` | HANZE country name. |
| `hanze_event_type` | HANZE flood type label, for example river or flash. |
| `hanze_flood_source` | HANZE flood-source label from the transformed table. |
| `italy_tri_high_hazard_hit` | `True` when the point intersects the Italian `HPH / elevata` hazard layer. |
| `flood_risk_area_value` | Simplified hazard label used by the Italy branch. Current values are `high` and `other`. |
| `hanze_spatial_hit` | Final spatial rule result. In this workflow it is equivalent to `italy_tri_high_hazard_hit` because the row already implies a HANZE match. |
| `hanze_hit_reason` | Final helper reason field. Current values are `hanze_and_tri_high` and `hanze_without_tri_high`. |
| `study_period_anchor_date` | Optional row-level anchor date copied into the output. |
| `study_period_primary_end_date` | Optional preferred row-level end date. |
| `study_period_fallback_end_date` | Optional fallback row-level end date. |
| `study_period_start` | Effective row-level start date. |
| `study_period_end` | Effective row-level end date. |
| `study_period_end_source` | Which source column supplied the effective end date. |

### 5.2 HANZE `event_hits`

This sheet is the positive subset of the HANZE `candidate_events` sheet.

A row is kept when:

- `hanze_spatial_hit = True`

Core columns are:

| Column | Meaning |
| --- | --- |
| `point_id` | Unique point identifier. |
| `excel_row_number` | Original Excel row number after header detection. |
| `point_latitude` | Point latitude used by the script. |
| `point_longitude` | Point longitude used by the script. |
| `lau_code` | LAU code matched to the point. |
| `lau_name` | LAU name matched to the point. |
| `nuts3_code` | NUTS3 code used for the HANZE match. |
| `nuts3_name` | NUTS3 name used for readability. |
| `study_period_end` | Effective row-level end date used to filter HANZE rows. |
| `study_period_end_source` | Which source column supplied the effective end date. |
| `hanze_event_uid` | Unique script-built HANZE row identifier. |
| `hanze_event_id` | Original HANZE event ID. |
| `hanze_start_date` | Standardized HANZE event start date. |
| `hanze_end_date` | Standardized HANZE event end date. |
| `hanze_country_code` | HANZE country code. |
| `hanze_country_name` | HANZE country name. |
| `hanze_event_type` | HANZE flood type. |
| `hanze_flood_source` | HANZE flood-source label. |
| `italy_tri_high_hazard_hit` | `True` when the point intersects the `HPH / elevata` hazard layer. |
| `flood_risk_area_value` | Simplified hazard label for the Italy branch. |
| `hanze_spatial_hit` | Final positive flag for the HANZE plus TRI branch. |
| `hanze_hit_reason` | Helper reason field explaining whether the row passed the final rule. |

## 6. Reading The Two Italy Workbooks Together

Recommended interpretation:

- JRC workbook:
  asks whether official flood rasters show a local or nearby hit
- HANZE plus TRI workbook:
  asks whether a point belongs to a HANZE-affected `NUTS3` region and also lies
  inside the Italian high-hazard flood layer

That means the two outputs are complementary, not interchangeable.

- JRC positive:
  raster-confirmed event evidence
- HANZE plus TRI positive:
  fallback screening evidence based on regional event linkage plus hazard-zone
  overlap

## 7. Quick Q&A

Question:

- does one row in `point_flags` mean one workbook row?

Answer:

- not exactly
- it means one unique `point_id`
- if the same coordinates appear twice with different IDs, they remain two
  separate point records

Question:

- does a HANZE `candidate_events` row already mean the point is positive?

Answer:

- no
- it means the point matched the HANZE event through `NUTS3` and the date logic
- the point becomes positive only when `italy_tri_high_hazard_hit = True`

Question:

- is `hanze_spatial_hit` different from `italy_tri_high_hazard_hit`?

Answer:

- in the current Italy workflow, no
- the HANZE match is already implied by being present in the candidate row
- so the final spatial decision reduces to whether the point intersects the
  high-hazard TRI geometry
