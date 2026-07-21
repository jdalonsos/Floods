# Flood Pipeline Master Guide

This is the main entry point for the current flood workflow documentation.

If you want to understand the whole process from raw point workbook to final
`FLOOD_LGD` output, start here.

The project currently supports four practical pipeline variants:

1. France T20
2. France collaterals
3. Italy T20
4. Italy collaterals

All four follow the same high-level pattern:

1. run a **check** script that builds source-specific checked workbooks
2. run a **build** script that consolidates those checked workbooks into one
   final `FLOOD_LGD` dataset

## 1. Recommended Reading Order

Read the docs in this order:

1. [docs/flood_pipeline_master_guide.md](D:/M2_MoSEF/DataCollection/docs/flood_pipeline_master_guide.md)
   - one-page overview of all current workflows
2. [docs/t20_flood_pipeline_guide.md](D:/M2_MoSEF/DataCollection/docs/t20_flood_pipeline_guide.md)
   - split between check step and build step
3. [docs/check_points_against_jrc_floods_deep_guide.md](D:/M2_MoSEF/DataCollection/docs/check_points_against_jrc_floods_deep_guide.md)
   - France JRC/GASPAR/HANZE checker logic in detail
4. [docs/check_italy_points_against_jrc_hanze_guide.md](D:/M2_MoSEF/DataCollection/docs/check_italy_points_against_jrc_hanze_guide.md)
   - Italy JRC/HANZE checker logic in detail
5. [docs/build_flood_lgd_exports_deep_guide.md](D:/M2_MoSEF/DataCollection/docs/build_flood_lgd_exports_deep_guide.md)
   - final `FLOOD_LGD` consolidation logic in detail

Supporting dictionaries:

- [docs/flood_workbook_column_dictionary.md](D:/M2_MoSEF/DataCollection/docs/flood_workbook_column_dictionary.md)
  - France check-workbook columns
- [docs/italy_flood_workbook_column_dictionary.md](D:/M2_MoSEF/DataCollection/docs/italy_flood_workbook_column_dictionary.md)
  - Italy check-workbook columns

## 2. Pipeline Matrix

| Workflow | Check script | Build script | Sources used in final build |
| --- | --- | --- | --- |
| France T20 | [src/check_points_against_jrc_floods.py](D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods.py) | [src/build_flood_lgd_exports.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports.py) | `JRC + GASPAR + HANZE` |
| France collaterals | [src/check_points_against_jrc_floods_collaterals.py](D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods_collaterals.py) | [src/build_flood_lgd_exports_collaterals.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_collaterals.py) | `JRC + GASPAR + HANZE` |
| Italy T20 | [src/check_italy_points_against_jrc_hanze.py](D:/M2_MoSEF/DataCollection/src/check_italy_points_against_jrc_hanze.py) | [src/build_flood_lgd_exports_italy.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_italy.py) | `JRC + HANZE` |
| Italy collaterals | [src/check_italy_points_against_jrc_hanze_collaterals.py](D:/M2_MoSEF/DataCollection/src/check_italy_points_against_jrc_hanze_collaterals.py) | [src/build_flood_lgd_exports_collaterals_italy.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_collaterals_italy.py) | `JRC + HANZE` |

## 3. Common Concepts

### 3.1 Check step versus build step

The **check** step keeps source-native event rows.

Examples:

- one row per `point_id x JRC event`
- one row per `point_id x GASPAR event`
- one row per `point_id x HANZE event`

The **build** step merges those checked source rows into final consolidated
episodes and writes the target `FLOOD_LGD` columns.

### 3.2 Final output granularity

The final `FLOOD_LGD` table is **not** one row per point.

It is one row per:

- `point_id x consolidated flood episode`

So one point can appear several times if it is linked to several distinct flood
episodes.

If a point has no flood at all, it still appears once with:

- `FLAG_FLOOD_ADR = 0`
- `FLAG_FLOOD_ADR_AREA = 0`
- `DATE_REF_FLOOD = NA`
- `DATE_END_FLOOD = NA`

### 3.3 Cross-source merge rule

Within one point:

- source rows are ordered chronologically
- rows are merged into the same consolidated episode when the gap between
  intervals stays within `30 days`
- otherwise they remain separate episodes

Retained source priority:

1. `JRC`
2. `GASPAR`
3. `HANZE`

For Italy workflows, the effective priority becomes:

1. `JRC`
2. `HANZE`

That priority controls:

- `FLOOD_DATA_SOURCE`
- `FLOOD_DATA_SOURCE_AREA`
- `DATE_REF_FLOOD`
- `DATE_END_FLOOD`
- JRC depth fields when the retained source is JRC

## 4. Point Identifier Logic

This is a key distinction between T20 and collateral workflows.

### France T20

- `point_id` normally comes from `#`

### Italy T20

- `point_id` normally comes from `#`

### France collaterals

- the pipeline now creates a **sequential row-level `point_id`**
- it does **not** use `ID_geoloc` as the final unique key

Reason:

- `ID_geoloc` can repeat across several rows
- `ID_geoloc` can also be empty
- the flood workflow needs one unique row identity per workbook row

### Italy collaterals

- the pipeline also creates a **sequential row-level `point_id`**
- `KEY_COLLATERAL` stays as a business label, not as the final unique row key

Reason:

- one collateral label can repeat on several coordinate rows

## 5. Date Logic By Workflow

There are two separate date questions:

1. which end date is used to **filter candidate events** during the check step?
2. which value is written into final `CLOSED_DEFAULT_DATE` in the LGD build?

Those are intentionally not always the same.

### France T20

Check step:

- preferred end = `Closed_Default_Date`
- fallback end = `Cut_off_Date`

Final LGD:

- `CLOSED_DEFAULT_DATE` comes from `Closed_Default_Date`
- if missing, the final exporter may use the configured fallback when the T20
  preset requests it

### France collaterals

Check step:

- preferred end = `Closed_Default_Date`
- fallback end = `Cut_off_Date`

Final LGD:

- `CLOSED_DEFAULT_DATE` comes from `Closed_Default_Date` only
- if `Closed_Default_Date` is empty, `CLOSED_DEFAULT_DATE` stays empty
- `Cut_off_Date` is **not** forced into the final LGD output field

### Italy T20

Check step:

- preferred end = `Closed_Default_Date`

Final LGD:

- `CLOSED_DEFAULT_DATE` comes from `Closed_Default_Date`
- `Default_Date` is also carried explicitly into the final LGD

### Italy collaterals

Check step:

- preferred end = `Closed_Default_Date`
- fallback end = `Cut_off_Date`

Final LGD:

- `CLOSED_DEFAULT_DATE` comes from `Closed_Default_Date` only
- if `Closed_Default_Date` is empty, `CLOSED_DEFAULT_DATE` stays empty
- `Default_Date` is carried explicitly into the final LGD

## 6. Source Workbook Shapes

### France collaterals source workbook

The current France collaterals presets expect a workbook shaped like:

- `lat`
- `lon`
- `Reference_Date`
- `Closed_Default_Date`
- `Cut_off_Date`
- `Default_Date`
- usually `Obligor_ID`
- usually `Facility_ID`

The source workbook may also contain `ID_geoloc`, but that field is no longer
used as the final unique `point_id`.

### Italy collaterals source workbook

The current Italy collaterals presets expect a workbook shaped like:

- `KEY_COLLATERAL`
- `lat`
- `lon`
- `Default_Date`
- `Closed_Default_Date`
- `Cut_off_Date`

`KEY_COLLATERAL` is kept as the business label and final `Facility_ID`.

## 7. CSV Output Convention

All `FLOOD_LGD` CSV outputs now use:

- semicolon separator `;`

Why:

- `ID_ADR` contains one text field built from latitude and longitude
- example: `41.09775000, 16.77685000`
- using `;` avoids wrapping that field in double quotes in normal CSV output

## 8. Progress Logging

The build step prints progress during clustering.

Useful options:

- `--progress-every-points`
- `--csv-chunk-size`

This is especially helpful for large T20 or collateral outputs where the final
merge can run for a long time.

## 9. Main Docs For Each Question

If your question is:

- "How does the France checker work?"
  - read [docs/check_points_against_jrc_floods_deep_guide.md](D:/M2_MoSEF/DataCollection/docs/check_points_against_jrc_floods_deep_guide.md)
- "How does the Italy checker work?"
  - read [docs/check_italy_points_against_jrc_hanze_guide.md](D:/M2_MoSEF/DataCollection/docs/check_italy_points_against_jrc_hanze_guide.md)
- "How does the final LGD build work?"
  - read [docs/build_flood_lgd_exports_deep_guide.md](D:/M2_MoSEF/DataCollection/docs/build_flood_lgd_exports_deep_guide.md)
- "What do the check-workbook columns mean?"
  - read [docs/flood_workbook_column_dictionary.md](D:/M2_MoSEF/DataCollection/docs/flood_workbook_column_dictionary.md)
  - and [docs/italy_flood_workbook_column_dictionary.md](D:/M2_MoSEF/DataCollection/docs/italy_flood_workbook_column_dictionary.md)
- "What is the short end-to-end story?"
  - read [docs/t20_flood_pipeline_guide.md](D:/M2_MoSEF/DataCollection/docs/t20_flood_pipeline_guide.md)

## 10. Current Status

The documentation and code are now aligned on these recent behaviors:

- France collaterals use row-level generated `point_id`
- Italy collaterals use row-level generated `point_id`
- France collaterals final `CLOSED_DEFAULT_DATE` stays empty when missing
- Italy collaterals final `CLOSED_DEFAULT_DATE` stays empty when missing
- Italy T20 final exporter carries `Default_Date` explicitly
- Italy collaterals final exporter carries `Default_Date` explicitly
- `src/add_nuts_to_flood_lgd.py` can enrich an existing FLOOD_LGD file with `nuts1`, `nuts2`, and `nuts3` fields directly from `ID_ADR`
- post-processing FLOOD_LGD helpers now auto-detect `;` or `,` input CSV files and preserve the detected separator on write
