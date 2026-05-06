# France JRC vs Gaspar Flexible Comparison (7-day variant)

This comparison used a date window of **7 days**.

## Open These First

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
- `details/`

## How To Read The Numbers

- `unique events` means unique `jrc_event_id` or unique `gaspar_event_uid`.
- `canonical rows` means one comparison row at the chosen level.
- for commune level, one canonical row is one commune-event row.
- for department level, one canonical row is one department-event row.
- unmatched row tables can be much larger than unmatched unique event counts because one event can be unmatched in many communes or departments.

## Detailed Audit Tables

- all detailed raw match tables, canonical tables, unmatched tables, parquet files, and diagnostics are stored in `details/`.

## Coverage Overview

- commune / unique_events: JRC matched 66 of 288, Gaspar matched 499 of 3505.
- commune / canonical_rows: JRC matched 2501 of 64327, Gaspar matched 1983 of 19217.
- department / unique_events: JRC matched 125 of 288, Gaspar matched 1488 of 3505.
- department / canonical_rows: JRC matched 691 of 2642, Gaspar matched 1902 of 5426.

## Quick Reading Path

1. Start with `comparison_summary.csv` for the headline counts.
2. Open `coverage_overview.csv` to distinguish unique event counts from row counts.
3. Open the best-match overview table(s) to review the strongest suggested event pairings.
4. Use the workbook and the detailed tables only when you need deeper audit or debugging.
