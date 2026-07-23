# Documentation Guide

This page is the documentation entry point for the Floods project. It is
designed for a reader who has just opened the repository and wants to
understand what the project does, how the pieces fit together, and where to go
next.

## Recommended reading order

Read these documents in order:

1. **[Project README](../README.md)** — purpose, supported components, setup,
   and the most common commands.
2. **This page** — repository map and documentation routes.
3. **[Geodata pipeline guide](geodata_pipeline_guide.md)** — the raster,
   administrative-boundary, CRS, and Europe-to-France processing concepts.
4. **[Flood pipeline master guide](flood_pipeline_master_guide.md)** — the
   current France/Italy and T20/collateral production workflows.
5. Choose the route that matches your work:
   - point checks: [France deep guide](check_points_against_jrc_floods_deep_guide.md)
     or [Italy guide](check_italy_points_against_jrc_hanze_guide.md);
   - final LGD exports:
     [build guide](build_flood_lgd_exports_deep_guide.md);
   - raster visualization:
     [dashboard guide](streamlit_raster_dashboard_deep_guide.md);
   - France JRC/GASPAR comparison:
     [commune activity app guide](france_commune_activity_app_deep_guide.md).
6. Consult the relevant
   [France column dictionary](flood_workbook_column_dictionary.md) or
   [Italy column dictionary](italy_flood_workbook_column_dictionary.md) while
   reading outputs.

If you only have ten minutes, read steps 1, 2, and 4.

## Project in one picture

```text
JRC flood rasters + administrative boundaries + national event sources
                              |
                              v
              Europe raster tabularization and lookups
                              |
              +---------------+----------------+
              |                                |
              v                                v
     France/Italy point checks        Raster and comparison apps
      (JRC, GASPAR, HANZE)              (inspection/audit)
              |
              v
       Source-specific evidence
              |
              v
       Consolidated FLOOD_LGD exports
```

The repository serves two related use cases:

- **geodata preparation and exploration**, which converts event rasters into
  administrative tables and visual previews;
- **portfolio flood assessment**, which checks point locations against flood
  evidence and consolidates the results into LGD-ready records.

## Repository map

| Path | Purpose | Newcomer guidance |
| --- | --- | --- |
| `src/` | Current Python pipelines, checkers, exporters, and apps | Start here for maintained implementation |
| `tests/` | Automated regression tests for core workflows | Use these to verify a change |
| `docs/` | Guides, dictionaries, audits, and deployment notes | Start with this file |
| `data/raw/` | Source datasets and reference layers | Often large; availability depends on the checkout |
| `data/processed/` | Reusable derived inputs and pipeline products | Generated or curated, depending on the dataset |
| `outputs/` | Reports and run-specific deliverables | Treat as generated results |
| `deploy/` | Deployment-specific files | Read only when deploying an app |
| `sandbox/` | Experiments and exploratory notebooks | Not the canonical production path |
| `drop/` | Superseded or retained historical work | Do not use as the default implementation |
| `src/old/` | Legacy scripts and notebooks | Reference only |

Large rasters, workbooks, and generated outputs are not all expected to be
version-controlled. Before running a pipeline, compare its documented input
paths with the files available in your local `data/` tree.

## Choose a documentation route

### A. Understand or run the Europe geodata pipeline

1. [Geodata pipeline guide](geodata_pipeline_guide.md)
2. `src/granular_tabularization.py --help`
3. `src/france_lau_to_insee.py --help` for France harmonization
4. [TRI reference](tri_2020_sig_di_reference.md) if working with French risk
   zones

### B. Produce France or Italy flood evidence and LGD exports

1. [Flood pipeline master guide](flood_pipeline_master_guide.md)
2. [T20 check/build guide](t20_flood_pipeline_guide.md)
3. The country-specific checker guide
4. [LGD export build guide](build_flood_lgd_exports_deep_guide.md)
5. The matching column dictionary

The essential execution sequence is:

```text
input point workbook
  -> country/workbook-specific check script
  -> JRC/GASPAR/HANZE checked workbooks
  -> country/workbook-specific build script
  -> consolidated FLOOD_LGD output
```

### C. Inspect rasters or compare France sources

1. [Raster dashboard guide](streamlit_raster_dashboard_deep_guide.md)
2. [France commune activity app guide](france_commune_activity_app_deep_guide.md)
3. [GASPAR all-dates workflow](gaspar_all_dates_workflow.md)
4. The bilingual audit reports listed below, if you need validation results

### D. Deploy an application

- [Streamlit Community Cloud](streamlit_community_cloud_deployment.md)
- [Render](render_deployment.md)
- [Oracle Always Free](oracle_always_free_streamlit_deployment.md)

Deployment documents assume that the corresponding app already runs locally.

## Documentation catalog

### Core technical guides

- [Geodata pipeline](geodata_pipeline_guide.md)
- [Flood pipeline master guide](flood_pipeline_master_guide.md)
- [T20 flood pipeline](t20_flood_pipeline_guide.md)
- [France point-check internals](check_points_against_jrc_floods_deep_guide.md)
- [Italy JRC/HANZE point checks](check_italy_points_against_jrc_hanze_guide.md)
- [LGD export internals](build_flood_lgd_exports_deep_guide.md)

### Schemas and source references

- [France workbook column dictionary](flood_workbook_column_dictionary.md)
- [Italy workbook column dictionary](italy_flood_workbook_column_dictionary.md)
- [French TRI dataset reference](tri_2020_sig_di_reference.md)

### Applications and deployment

- [Raster dashboard](streamlit_raster_dashboard_deep_guide.md)
- [France commune activity app](france_commune_activity_app_deep_guide.md)
- [Streamlit Community Cloud deployment](streamlit_community_cloud_deployment.md)
- [Render deployment](render_deployment.md)
- [Oracle deployment](oracle_always_free_streamlit_deployment.md)

### Validation and audit reports

- [JRC/GASPAR match audit — English](gaspar_jrc_match_audit_en.md)
- [JRC/GASPAR match audit — French](gaspar_jrc_match_audit_fr.md)
- [2015–2024 horizon audit — English](gaspar_jrc_horizon_audit_en.md)
- [2015–2024 horizon audit — French](gaspar_jrc_horizon_audit_fr.md)
- [July 2021 mismatch evidence](july_2021_gaspar_jrc_mismatch_evidence_report.md)

These reports document specific analyses and should not replace the core
pipeline guides.

## First local verification

From the repository root:

```bash
python --version
python -m pip install -r requirements-pip.txt
python -m pytest -q
```

The project targets Python 3.12 (`.python-version` and `pyproject.toml`). Some
geospatial runs also require local source data that is too large or unsuitable
for Git. A successful dependency installation does not by itself provide those
datasets.

Before a long run, inspect the relevant command line:

```bash
python src/granular_tabularization.py --help
python src/check_points_against_jrc_floods.py --help
python src/build_flood_lgd_exports.py --help
```

Use the wrapper variants described in the master guide for Italy and collateral
workbooks.

## How to read generated results

1. Confirm the run log and output path.
2. Identify whether the file is source-specific evidence or a consolidated LGD
   export.
3. Check its row granularity; final LGD output is generally one row per
   `point_id × consolidated flood episode`, not one row per point.
4. Use the appropriate column dictionary.
5. Keep the distinction between point-level and surrounding-area flood flags.
6. Record the command, input versions, and date window used for reproducibility.

## Documentation maintenance rule

When changing a workflow:

1. update its `--help` text and the closest technical guide;
2. update a column dictionary if the output schema changes;
3. update this index if a new canonical guide or workflow is introduced;
4. use repository-relative Markdown links so documentation works on GitHub and
   in a local clone;
5. run the relevant tests and check all changed links before publishing.
