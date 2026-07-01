from __future__ import annotations

import argparse
from pathlib import Path

from check_points_against_jrc_floods import build_argument_parser, run


DEFAULT_OUTPUT = Path("data/processed/france_points_jrc_flood_check_collaterals.xlsx")


def build_collaterals_argument_parser() -> argparse.ArgumentParser:
    parser = build_argument_parser()
    parser.description = (
        "Check France collateral coordinates against JRC, GASPAR, and HANZE using "
        "T20-style collateral columns such as ID_geoloc, lat, lon, Reference_Date, "
        "Closed_Default_Date, and Cut_off_Date. By default, the study window keeps "
        "the full event history up to each row's Closed_Default_Date, falling back "
        "to Cut_off_Date when needed."
    )
    parser.set_defaults(
        latitude_col="lat",
        longitude_col="lon",
        point_id_col="ID_geoloc",
        city_col="Facility_ID",
        row_study_anchor_col="Reference_Date",
        row_study_end_col="Closed_Default_Date",
        row_study_end_fallback_col="Cut_off_Date",
        out_file=str(DEFAULT_OUTPUT),
    )
    return parser


def main() -> None:
    parser = build_collaterals_argument_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
