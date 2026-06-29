from __future__ import annotations

import argparse
from pathlib import Path

from check_italy_points_against_jrc_hanze import build_argument_parser, run


DEFAULT_OUTPUT = Path("data/processed/italy_points_jrc_flood_check_collaterals.xlsx")


def build_italy_collaterals_argument_parser() -> argparse.ArgumentParser:
    parser = build_argument_parser()
    parser.description = (
        "Check Italy collateral coordinates against processed JRC flood events and "
        "against HANZE plus Italy TRI high-hazard polygons. By default, the script "
        "creates a sequential point_id per workbook row, keeps KEY_COLLATERAL as the "
        "point label, and retains events from 2000-01-01 through each row's last_date."
    )
    parser.set_defaults(
        latitude_col="lat",
        longitude_col="lon",
        point_id_col=None,
        city_col="KEY_COLLATERAL",
        row_study_end_col="last_date",
        study_start="2000-01-01",
        out_file=str(DEFAULT_OUTPUT),
    )
    return parser


def main() -> None:
    parser = build_italy_collaterals_argument_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
