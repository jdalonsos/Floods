from __future__ import annotations

import argparse
from pathlib import Path

from build_flood_lgd_exports import build_argument_parser, run


DEFAULT_JRC_WORKBOOK = Path("data/processed/france_points_jrc_flood_check_collaterals.xlsx")
DEFAULT_GASPAR_WORKBOOK = Path("data/processed/france_points_gaspar_check_collaterals.xlsx")
DEFAULT_HANZE_WORKBOOK = Path("data/processed/france_points_hanze_check_collaterals.xlsx")


def build_collaterals_export_argument_parser() -> argparse.ArgumentParser:
    parser = build_argument_parser()
    parser.description = (
        "Build a consolidated FLOOD_LGD export for collateral-style workbooks that "
        "use ID_geoloc, lat, lon, Reference_Date, Closed_Default_Date, and "
        "Cut_off_Date columns. The wrapper recreates the row-level point_id used "
        "by the collateral flood-check step instead of grouping directly by ID_geoloc."
    )
    parser.set_defaults(
        source_workbook=None,
        source_point_id_col=None,
        source_latitude_col="lat",
        source_longitude_col="lon",
        source_closed_default_col="Closed_Default_Date",
        source_closed_default_fallback_col=None,
        source_default_date_col="Default_Date",
        source_obligor_id_col="Obligor_ID",
        source_facility_id_col="Facility_ID",
        source_type_adr_value="Collateral",
        jrc_workbook=str(DEFAULT_JRC_WORKBOOK),
        gaspar_workbook=str(DEFAULT_GASPAR_WORKBOOK),
        hanze_workbook=str(DEFAULT_HANZE_WORKBOOK),
    )
    return parser


def main() -> None:
    parser = build_collaterals_export_argument_parser()
    args = parser.parse_args()
    if not args.source_workbook:
        parser.error("--source-workbook is required for the collateral FLOOD_LGD preset.")
    run(args)


if __name__ == "__main__":
    main()
