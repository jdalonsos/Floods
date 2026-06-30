# T20 Flood Pipeline Guide

This guide explains the split between the two scripts used for the T20 flood workflow:

- [src/check_points_against_jrc_floods.py](D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods.py)
- [src/build_flood_lgd_exports.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports.py)

Italy uses the same split with its own wrappers:

- [src/check_italy_points_against_jrc_hanze.py](D:/M2_MoSEF/DataCollection/src/check_italy_points_against_jrc_hanze.py)
- [src/build_flood_lgd_exports_italy.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports_italy.py)

For a detailed internal walkthrough of the consolidation script itself, see:

- [docs/build_flood_lgd_exports_deep_guide.md](D:/M2_MoSEF/DataCollection/docs/build_flood_lgd_exports_deep_guide.md)

The short answer is:

- `check_points_against_jrc_floods.py` now produces **three source-specific checked datasets/workbooks**
  - `JRC`
  - `GASPAR`
  - `HANZE`
- `build_flood_lgd_exports.py` consumes those three checked datasets and produces **one consolidated T20 export**
  - `FLOOD_LGD`

## 1. What Each Script Does

### Script A: `check_points_against_jrc_floods.py`

This is the **source-building step**.

Its role is to prepare the flood evidence source by source, while keeping the native event granularity of each source.

It writes three checked workbooks:

1. JRC checked workbook
   - default family: `*_jrc_flood_check.xlsx`
   - contains JRC raster-based candidates and hits

2. GASPAR checked workbook
   - default family: `*_gaspar_check.xlsx`
   - contains commune-level Gaspar candidates and the subset that pass the France TRI/riparian point rule

3. HANZE checked workbook
   - default family: `*_hanze_check.xlsx`
   - contains department-level HANZE candidates and the subset that pass the France TRI/riparian point rule

For GASPAR and HANZE, the script does **not** collapse to one row per point.
It keeps one row per `point_id x candidate_event`, then derives the point-positive subset in the `event_hits` sheet.

### Script B: `build_flood_lgd_exports.py`

This is the **consolidation step**.

Its role is to merge the checked JRC/GASPAR/HANZE evidence into **one final T20 table** with the target columns such as:

- `point_id`
- `Obligor_ID`
- `Flag_JRC`
- `Flag_GASPAR`
- `Flag_HANZE`
- `FLOOD_DATA_SOURCE`
- `FLAG_FLOOD_ADR`
- `FLAG_FLOOD_ADR_AREA`
- `DATE_REF_FLOOD`
- `DATE_END_FLOOD`

This script outputs **one final dataset**, not three.

If you run the exporter in `--mode csv`, the output is now semicolon-separated.

That is intentional because:

- `ID_ADR` stores latitude and longitude in one text cell
- so values look like `48.10000000, 2.10000000`
- using `;` avoids unnecessary double quotes around that field in CSV output

## 2. Granularity

The final export is **not** one row per point.

It is one row per:

- `point_id x consolidated flood episode`

So if a point is linked to multiple distinct flood episodes, it can appear multiple times in the final `FLOOD_LGD` table.

If a point has no associated flood in any source, it still appears once with:

- `FLAG_FLOOD_ADR = 0`
- `FLAG_FLOOD_ADR_AREA = 0`
- `DATE_REF_FLOOD = NA`
- `DATE_END_FLOOD = NA`

## 3. Source Rules Used Before Consolidation

### JRC

JRC is the raster-confirmed source.

- point level:
  positive when the `40 m` point buffer is flooded
- area level:
  positive when the `1 km` area buffer is flooded

### GASPAR

GASPAR is commune-based and uses the France TRI/riparian location rule.

- candidate level:
  one row per `point_id x GASPAR event`
- point-positive rule:
  - `high` flood-risk area -> positive
  - `other` flood-risk area -> negative
  - `out` of TRI -> positive only if the point is in a riparian zone

### HANZE

HANZE is department-based and uses the same France TRI/riparian location rule.

- candidate level:
  one row per `point_id x HANZE event`
- point-positive rule:
  - `high` flood-risk area -> positive
  - `other` flood-risk area -> negative
  - `out` of TRI -> positive only if the point is in a riparian zone

## 4. Area-Level Meaning

The area-level flags do not apply the point-location constraint in the same way as the point-level flags.

They are derived from source candidates:

- `Flag_JRC_AREA`
  - positive when JRC detects a flood in the surrounding area
- `Flag_GASPAR_AREA`
  - positive when a GASPAR candidate event exists for the point's commune
- `Flag_HANZE_AREA`
  - positive when a HANZE candidate event exists for the point's department

## 5. Cross-Source Consolidation Rule

The final exporter combines the three checked sources together:

- `JRC`
- `GASPAR`
- `HANZE`

For each point, events are grouped into consolidated flood episodes using this rule:

- if the start or end of one flood is within `30 days` of another flood, they are treated as the same consolidated episode
- otherwise they stay as different episodes

Within one consolidated episode, the retained source priority is:

1. `JRC`
2. `GASPAR`
3. `HANZE`

That priority is used for:

- `FLOOD_DATA_SOURCE`
- `FLOOD_DATA_SOURCE_AREA`
- the dates retained in `DATE_REF_FLOOD` and `DATE_END_FLOOD`
- JRC depth fields when the retained source is JRC

## 6. Meaning of the Final Flags

At consolidated-episode level:

- `FLAG_FLOOD_ADR = 1`
  - if at least one point-level source is positive in the merged episode
- `FLAG_FLOOD_ADR_AREA = 1`
  - if at least one area-level source is positive in the merged episode

Equivalent source-specific logic:

- `FLAG_FLOOD_ADR = 1` if `Flag_JRC + Flag_GASPAR + Flag_HANZE > 0`
- `FLAG_FLOOD_ADR_AREA = 1` if `Flag_JRC_AREA + Flag_GASPAR_AREA + Flag_HANZE_AREA > 0`

## 7. Practical Sequence

For T20, the intended sequence is:

1. Run `check_points_against_jrc_floods.py`
2. Produce the three checked workbooks:
   - JRC
   - GASPAR
   - HANZE
3. Run `build_flood_lgd_exports.py`
4. Produce one final consolidated `FLOOD_LGD` dataset

## 8. Key Functions

Useful anchors in the code:

- HANZE candidate dataset builder:
  [src/check_points_against_jrc_floods.py](D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods.py:2281)
- HANZE hit subset:
  [src/check_points_against_jrc_floods.py](D:/M2_MoSEF/DataCollection/src/check_points_against_jrc_floods.py:2443)
- Final T20 consolidated export:
  [src/build_flood_lgd_exports.py](D:/M2_MoSEF/DataCollection/src/build_flood_lgd_exports.py:588)

## 9. Current Status

The implementation now follows this split:

- **three source-specific checked datasets** from `check_points_against_jrc_floods.py`
- **one consolidated final T20 dataset** from `build_flood_lgd_exports.py`

For Italy, the equivalent split is:

- **two source-specific checked datasets** from `check_italy_points_against_jrc_hanze.py`
  - `JRC`
  - `HANZE`
- **one consolidated final T20 dataset** from `build_flood_lgd_exports_italy.py`
  - source priority `JRC > HANZE`
  - same `30-day` merge rule
