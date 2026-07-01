from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from build_flood_lgd_exports import (
    build_argument_parser,
    build_flood_lgd_dataframe,
    build_output_path,
    ensure_required_file,
    load_source_frame,
    log_progress,
    read_workbook_sheet,
    write_csv_output,
    write_sheet_into_existing_workbook,
    write_standalone_workbook,
)


DEFAULT_JRC_WORKBOOK = Path("data/processed/italy_points_jrc_flood_check_collaterals.xlsx")
DEFAULT_HANZE_WORKBOOK = Path("data/processed/italy_points_hanze_tri_check_collaterals.xlsx")


def build_italy_collaterals_export_argument_parser() -> argparse.ArgumentParser:
    parser = build_argument_parser()
    parser.description = (
        "Build a consolidated FLOOD_LGD export for Italy collateral-style workbooks "
        "that use KEY_COLLATERAL, lat, lon, and last_date columns. The final "
        "consolidation uses JRC plus HANZE evidence only, merges source rows with the "
        "same 30-day rule, and retains source priority JRC > HANZE."
    )
    parser.set_defaults(
        source_workbook=None,
        source_point_id_col=None,
        source_latitude_col="lat",
        source_longitude_col="lon",
        source_closed_default_col="last_date",
        source_default_date_col="Default_Date",
        source_facility_id_col="KEY_COLLATERAL",
        source_type_adr_value="Collateral",
        gaspar_workbook=None,
        jrc_workbook=str(DEFAULT_JRC_WORKBOOK),
        hanze_workbook=str(DEFAULT_HANZE_WORKBOOK),
    )
    return parser


def run(args: argparse.Namespace) -> None:
    verbose = not args.quiet

    if not args.source_workbook:
        raise ValueError("Missing required source workbook path.")

    source_workbook = Path(args.source_workbook)
    jrc_workbook = Path(args.jrc_workbook)
    hanze_workbook = Path(args.hanze_workbook)
    output_dir = Path(args.output_dir)

    ensure_required_file(source_workbook, "source workbook")
    ensure_required_file(jrc_workbook, "JRC workbook")
    if not hanze_workbook.exists():
        log_progress(
            f"HANZE workbook not found at {hanze_workbook}. HANZE columns will stay zero/NA.",
            enabled=verbose,
        )

    log_progress(f"Loading source workbook from {source_workbook}...", enabled=verbose)
    source_df = load_source_frame(
        source_workbook,
        sheet_name=args.source_sheet_name,
        point_id_col=args.source_point_id_col,
        latitude_col=args.source_latitude_col,
        longitude_col=args.source_longitude_col,
        closed_default_col=args.source_closed_default_col,
        obligor_id_col=args.source_obligor_id_col,
        facility_id_col=args.source_facility_id_col,
        type_adr_col=args.source_type_adr_col,
        default_type_adr=args.source_type_adr_value,
    )
    log_progress(f"Loaded source workbook with {len(source_df):,} rows.", enabled=verbose)

    jrc_event_hits = read_workbook_sheet(jrc_workbook, "event_hits", label="JRC event hits", verbose=verbose)
    hanze_candidates = read_workbook_sheet(
        hanze_workbook,
        "candidate_events",
        label="HANZE candidate events",
        verbose=verbose,
    )
    hanze_hits = read_workbook_sheet(hanze_workbook, "event_hits", label="HANZE event hits", verbose=verbose)

    log_progress("Starting Italy collateral FLOOD_LGD consolidation...", enabled=verbose)
    flood_lgd_df = build_flood_lgd_dataframe(
        source_df=source_df,
        jrc_event_hits=jrc_event_hits,
        gaspar_candidates=pd.DataFrame(),
        gaspar_hits=pd.DataFrame(),
        hanze_candidates=hanze_candidates,
        hanze_hits=hanze_hits,
        merge_gap_days=args.merge_gap_days,
        progress_every_points=args.progress_every_points,
        verbose=verbose,
    )

    output_path = output_dir / build_output_path(source_workbook, args.sheet_name, args.mode)
    if args.mode == "copy":
        log_progress(f"Writing Excel copy output to {output_path}...", enabled=verbose)
        write_sheet_into_existing_workbook(
            source_workbook,
            output_path,
            args.sheet_name,
            flood_lgd_df,
            replace_sheet=args.replace_sheet,
        )
    elif args.mode == "standalone":
        log_progress(f"Writing standalone workbook to {output_path}...", enabled=verbose)
        write_standalone_workbook(output_path, args.sheet_name, flood_lgd_df)
    elif args.mode == "csv":
        write_csv_output(
            output_path,
            flood_lgd_df,
            chunk_size=args.csv_chunk_size,
            verbose=verbose,
        )
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")

    print(f"Done. Output written to: {output_path.resolve()}")


def main() -> None:
    parser = build_italy_collaterals_export_argument_parser()
    args = parser.parse_args()
    if not args.source_workbook:
        parser.error("--source-workbook is required for the Italy collateral FLOOD_LGD preset.")
    run(args)


if __name__ == "__main__":
    main()
