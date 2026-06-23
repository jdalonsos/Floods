from __future__ import annotations

import argparse
from pathlib import Path

from check_points_against_jrc_floods import build_argument_parser, run


DEFAULT_OUTPUT = Path("data/processed/france_points_jrc_flood_check_collaterals.xlsx")


def build_collaterals_argument_parser() -> argparse.ArgumentParser:
    parser = build_argument_parser()
    parser.description = (
        "Check point coordinates against processed JRC flood events for workbooks that "
        "use ID_geoloc, lat, lon, and last_date columns. By default, the script keeps "
        "events from 2000-01-01 through each row's last_date."
    )
    parser.set_defaults(
        latitude_col="lat",
        longitude_col="lon",
        point_id_col="ID_geoloc",
        row_study_end_col="last_date",
        study_start="2000-01-01",
        out_file=str(DEFAULT_OUTPUT),
    )
    return parser


def main() -> None:
    parser = build_collaterals_argument_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
