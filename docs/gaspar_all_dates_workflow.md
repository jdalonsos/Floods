# Gaspar Full-History Workflow

This document explains the new full-history Gaspar preprocessing path used by the current BCEF flood workflow.

It focuses on two things:

- how the raw Gaspar source is now transformed from `data/raw/catnat_gaspar.csv`
- what changed in each code file to support that full-history workflow

## 1. Why This Change Was Made

Previously, the Gaspar fallback branch used:

- `data/processed/Gaspar_2015_2024.xlsx`

That workbook came from a preprocessing step limited to the `2015-2024` period.

For the current flood mapping, that was too restrictive.

The new workflow now starts from:

- `data/raw/catnat_gaspar.csv`

and keeps the full available history, while still filtering to the flood-related Gaspar risk labels.

## 2. New End-To-End Flow

The current full-history Gaspar flow is:

1. Read the raw Gaspar CSV from `data/raw/catnat_gaspar.csv`.
2. Keep only the flood-related `lib_risque_jo` labels:
   - `Inondations et/ou Coulées de Boue`
   - `Inondations Remontée Nappe`
   - `Chocs Mécaniques liés à l'action des Vagues`
3. Do not apply the old `2015-01-01` to `2024-12-31` source filter anymore.
4. Parse `dat_deb` and `dat_fin`.
5. Drop rows missing the core event fields.
6. Build the canonical Gaspar event key:
   - `gaspar_event_uid = cod_nat_catnat + gaspar_start_date + gaspar_end_date`
7. Resolve raw commune codes and names to current INSEE communes using:
   - the current France lookup
   - the historical INSEE update table
8. Write the full-history processed outputs under:
   - `data/processed/gaspar_all_dates/`
9. Use that processed workbook as the default Gaspar source inside:
   - `src/check_points_against_jrc_floods.py`

Important:

- the source is now full-history
- but the point-level flood check still applies the existing row-level end-date logic in the T20 workflow
- so we changed the Gaspar source horizon, not the T20 row filtering logic

## 3. Output Files

The new preprocessing step writes:

- `data/processed/gaspar_all_dates/Gaspar_all_dates.xlsx`
- `data/processed/gaspar_all_dates/gaspar_all_dates_resolved_current_communes.csv`
- `data/processed/gaspar_all_dates/gaspar_all_dates_diagnostics.json`

Workbook sheets:

- `GasparAllDatesFloodsClean`
- `Gaspar20152024FloodsClean`
- `GasparAllDatesResolved`
- `Diagnostics`

Compatibility note:

- the builder writes both `GasparAllDatesFloodsClean` and the legacy-compatible `Gaspar20152024FloodsClean`
- this lets older code paths still read the workbook without forcing an immediate sheet-name rewrite everywhere

## 4. File-By-File Changes

### 4.1 `src/france_commune_activity.py`

This file is where the main preprocessing logic changed.

What changed:

- Added new full-history constants:
  - `DEFAULT_GASPAR_FULL_HISTORY_DIR`
  - `DEFAULT_GASPAR_FULL_HISTORY_PROCESSED_PATH`
  - `DEFAULT_GASPAR_FULL_HISTORY_SHEET`
- Added `detect_csv_separator()`
  - this is needed because `data/raw/catnat_gaspar.csv` is semicolon-separated
- Updated `read_table()`
  - CSV reading is now separator-aware instead of assuming the default comma separator
- Added `normalize_risk_label()`
  - risk labels are normalized more robustly before filtering
- Updated `prepare_raw_gaspar_rows()`
  - the old hard source filter `2015-2024` was removed
  - the flood-risk filter remains
  - optional date bounds are still supported as parameters, but they are no longer applied by default
  - diagnostics were updated to reflect the new full-history logic

What did not change:

- the commune-resolution logic itself
- the current-code match
- the historical-code update logic
- the unique-name fallback logic
- the `gaspar_event_uid` construction rule

In short:

- `src/france_commune_activity.py` now supports a full-history raw Gaspar transform
- without changing the core commune harmonization logic

### 4.2 `src/build_gaspar_all_dates.py`

This is a new file.

Its role:

- build the new full-history Gaspar products from the raw CSV

What it does:

1. reads `data/raw/catnat_gaspar.csv`
2. applies the flood-related risk filter
3. keeps the full available history
4. resolves current communes
5. writes the processed workbook
6. writes a resolved CSV
7. writes a diagnostics JSON

Why this file exists:

- so the full-history Gaspar preprocessing is explicit and reproducible
- so another PC can regenerate the processed source from raw data
- so `check_points_against_jrc_floods.py` does not have to rebuild the workbook itself every time

### 4.3 `src/check_points_against_jrc_floods.py`

This file was updated only at the integration layer.

What changed:

- the default `--gaspar-file` now points to:
  - `data/processed/gaspar_all_dates/Gaspar_all_dates.xlsx`
- the CLI help text now explains that the default Gaspar source is the new full-history processed workbook
- the CLI help for `--gaspar-sheet-name` now notes that the builder writes a legacy-compatible sheet name too

What did not change:

- the Gaspar commune matching logic used during the point check
- the TRI / riparian logic
- the row-level temporal filter used in the T20 flood check

So this file did not change the Gaspar decision rule itself.

It only changed:

- which processed Gaspar workbook is used by default

### 4.4 `tests/test_france_commune_activity.py`

This file received a new regression test.

What changed:

- added a test proving that `prepare_raw_gaspar_rows()`:
  - reads a semicolon-separated CSV correctly
  - keeps full-history flood rows such as `1987`
  - filters out non-flood hazards such as `Glissement de Terrain`

Why this matters:

- it protects the exact change requested for the raw full-history Gaspar source
- it makes the semicolon CSV handling and the removal of the `2015-2024` cut testable

### 4.5 `data/raw/catnat_gaspar.csv`

This file did not need a content change.

What changed in practice:

- it is now the primary raw source for the fallback Gaspar flood workflow
- the repo already tracked it before
- the new code now uses it directly for rebuilding the processed Gaspar dataset

### 4.6 `data/processed/gaspar_all_dates/*`

These are new generated outputs.

Their role:

- provide a rerun-ready processed Gaspar source for another machine
- make the full-history fallback workflow reproducible without reusing the old `Gaspar_2015_2024.xlsx`

## 5. What Stayed The Same

The following logic did not change:

- the JRC raster logic
- the `40 m` point buffer logic
- the `1 km` surrounding buffer logic
- the simplified Gaspar spatial selection:
  - `TRI For`
  - or `outside n_tri` and `inside riparian`
- the T20 row-level date filtering inside `check_points_against_jrc_floods.py`

So the major change is:

- new Gaspar source horizon

not:

- a new flood-flag rule

## 6. Run Commands

### 6.1 Build the full-history Gaspar source

```bash
cd /d/M2_MoSEF/DataCollection

export PYTHONPATH="$PWD/.venv/Lib/site-packages"
export PROJ_LIB="$PWD/.venv/Lib/site-packages/rasterio/proj_data"
export GDAL_DATA="$PWD/.venv/Lib/site-packages/rasterio/gdal_data"

./.venv/Scripts/python.exe src/build_gaspar_all_dates.py
```

### 6.2 Run the flood check using that source

```bash
./.venv/Scripts/python.exe src/check_points_against_jrc_floods.py \
  --points-file data/processed/T20_Anonymised.xlsx \
  --latitude-col LAT \
  --longitude-col LONG \
  --lau-file data/raw/LAU_RG_01M_2024_4326.gpkg \
  --events-file data/processed/_outputs_eurostat_full/events_lau_long.parquet \
  --flood-dir data/JRC_flood_depth_maps \
  --france-lookup-file data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv \
  --france-old-insee-updates-file data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv \
  --gaspar-file data/processed/gaspar_all_dates/Gaspar_all_dates.xlsx \
  --gaspar-sheet-name GasparAllDatesFloodsClean \
  --tri-archive data/raw/tri_2020_sig_di \
  --riparian-root data/raw/France_Riparian \
  --row-study-anchor-col Reference_Date \
  --row-study-end-col Closed_Default_Date \
  --row-study-end-fallback-col Cut_off_Date \
  --out-file data/processed/T20_Anonymised_jrc_flood_check.xlsx
```

## 7. Bottom Line

The full-history Gaspar migration changed the data source, not the flood-flag logic.

Main result:

- old source:
  `data/processed/Gaspar_2015_2024.xlsx`
- new source:
  `data/raw/catnat_gaspar.csv` -> `data/processed/gaspar_all_dates/Gaspar_all_dates.xlsx`

Most important code changes:

- `src/france_commune_activity.py`:
  full-history raw transform and semicolon CSV support
- `src/build_gaspar_all_dates.py`:
  new reproducible builder
- `src/check_points_against_jrc_floods.py`:
  default Gaspar source switched to the new processed workbook
- `tests/test_france_commune_activity.py`:
  regression coverage for the new behavior
