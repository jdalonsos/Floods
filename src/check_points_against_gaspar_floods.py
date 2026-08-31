from __future__ import annotations

import argparse
from pathlib import Path

from compare_france_jrc_gaspar_flexible import normalize_insee_code_series
from check_points_against_jrc_floods import (
    DEFAULT_FRANCE_LOOKUP,
    DEFAULT_FRANCE_OLD_INSEE_UPDATES,
    DEFAULT_FRANCE_POINT_FILE,
    DEFAULT_GASPAR_FILE,
    DEFAULT_GASPAR_SHEET,
    DEFAULT_LAU_FILE,
    DEFAULT_RIPARIAN_ROOT,
    DEFAULT_TRI_ARCHIVE,
    ROW_STUDY_PERIOD_OUTPUT_COLUMNS,
    attach_france_lookup,
    build_detailed_sheet,
    build_gaspar_candidate_events,
    build_gaspar_candidate_sheet,
    build_gaspar_hits_sheet,
    build_point_flag_sheet,
    build_points_gdf,
    build_row_level_study_periods,
    classify_points_against_tri,
    filter_records_by_global_interval,
    load_points_table,
    load_resolved_gaspar_events,
    map_points_to_lau,
    write_gaspar_output_workbook,
)
from granular_tabularization import load_lau


DEFAULT_OUTPUT = Path("data/processed/france_points_gaspar_check.xlsx")


def derive_gaspar_only_output_path(points_file: Path) -> Path:
    return points_file.with_name(f"{points_file.stem}_gaspar_check.xlsx")


def resolve_output_path(points_file: Path, out_file: str | None) -> Path:
    if out_file and str(out_file).strip():
        return Path(out_file)
    return derive_gaspar_only_output_path(points_file)


def ensure_required_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label}: {path}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run only the Gaspar + TRI + riparian flood workflow, without the JRC raster checks. "
            "The output workbook keeps the same Gaspar sheets as the full pipeline."
        )
    )
    parser.add_argument("--points-file", default=str(DEFAULT_FRANCE_POINT_FILE), help="Input Excel workbook with latitude and longitude columns.")
    parser.add_argument("--sheet-name", default=None, help="Optional sheet name. Default uses the first sheet.")
    parser.add_argument("--latitude-col", default="Latitude", help="Latitude column name or alias. Default: Latitude.")
    parser.add_argument("--longitude-col", default="Longitude", help="Longitude column name or alias. Default: Longitude.")
    parser.add_argument("--point-id-col", default="#", help="Point identifier column. Default: #.")
    parser.add_argument("--city-col", default="City", help="Optional point label column. Default: City.")
    parser.add_argument("--lau-file", default=str(DEFAULT_LAU_FILE), help="Path to the Eurostat LAU GeoPackage.")
    parser.add_argument("--lau-country-filter", default="FR", help="Optional country filter for the LAU layer. Use FR for France or leave blank for all.")
    parser.add_argument("--france-lookup-file", default=str(DEFAULT_FRANCE_LOOKUP), help="France LAU to INSEE lookup CSV used to map points to current communes.")
    parser.add_argument(
        "--gaspar-file",
        default=str(DEFAULT_GASPAR_FILE),
        help=(
            "Processed Gaspar workbook used for the commune event matching. "
            "Default points to the full-history flood-only workbook built from raw/catnat_gaspar.csv."
        ),
    )
    parser.add_argument(
        "--gaspar-sheet-name",
        default=DEFAULT_GASPAR_SHEET,
        help=(
            f"Sheet name to read from the Gaspar workbook. Default: {DEFAULT_GASPAR_SHEET}. "
            "The full-history builder also writes this legacy-compatible sheet name."
        ),
    )
    parser.add_argument("--france-old-insee-updates-file", default=str(DEFAULT_FRANCE_OLD_INSEE_UPDATES), help="Historical old-INSEE to current-INSEE CSV used to resolve Gaspar communes.")
    parser.add_argument("--tri-archive", default=str(DEFAULT_TRI_ARCHIVE), help="National TRI source. Only the plain TRI For polygons and the n_tri territory boundaries are used.")
    parser.add_argument("--riparian-root", default=str(DEFAULT_RIPARIAN_ROOT), help="Root folder containing the unzipped France riparian shapefiles.")
    parser.add_argument("--study-start", default=None, help="Optional global study-period start date (YYYY-MM-DD). Keeps only Gaspar events whose intervals overlap this bound.")
    parser.add_argument("--study-end", default=None, help="Optional global study-period end date (YYYY-MM-DD). Keeps only Gaspar events whose intervals overlap this bound.")
    parser.add_argument("--row-study-anchor-col", default=None, help="Optional workbook column used as the per-row anchor date when a lookback window is requested.")
    parser.add_argument("--row-study-end-col", default=None, help="Optional workbook column used as the preferred per-row study-period end date.")
    parser.add_argument("--row-study-end-fallback-col", default=None, help="Optional fallback workbook column used when the preferred per-row end date is empty.")
    parser.add_argument("--row-study-lookback-years", type=int, default=None, help="Optional years to subtract from the per-row anchor date. Leave blank to keep the full flood history up to the row end date.")
    parser.add_argument("--out-file", default=None, help="Gaspar output workbook. Default derives <points_file_stem>_gaspar_check.xlsx next to the points workbook.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    points_file = Path(args.points_file)
    lau_file = Path(args.lau_file)
    france_lookup_file = Path(args.france_lookup_file)
    gaspar_file = Path(args.gaspar_file)
    france_old_insee_updates_file = Path(args.france_old_insee_updates_file)
    tri_archive = Path(args.tri_archive)
    riparian_root = Path(args.riparian_root)
    out_file = resolve_output_path(points_file, args.out_file)

    ensure_required_path(points_file, "points workbook")
    ensure_required_path(lau_file, "LAU layer")
    ensure_required_path(france_lookup_file, "France lookup CSV")
    ensure_required_path(gaspar_file, "Gaspar workbook")
    ensure_required_path(france_old_insee_updates_file, "historical INSEE updates CSV")
    ensure_required_path(tri_archive, "TRI source")
    ensure_required_path(riparian_root, "riparian root")

    target_countries = None
    if args.lau_country_filter and args.lau_country_filter.strip():
        target_countries = {code.strip().upper() for code in args.lau_country_filter.split(",") if code.strip()}

    print("Loading point workbook...")
    points_df, point_columns = load_points_table(
        workbook_path=points_file,
        sheet_name=args.sheet_name,
        latitude_col=args.latitude_col,
        longitude_col=args.longitude_col,
        point_id_col=args.point_id_col,
        city_col=args.city_col,
    )
    points_df, row_study_period_columns = build_row_level_study_periods(
        points_df,
        anchor_col=args.row_study_anchor_col,
        end_col=args.row_study_end_col,
        fallback_end_col=args.row_study_end_fallback_col,
        lookback_years=args.row_study_lookback_years,
    )
    print(f"Loaded {len(points_df):,} valid points.")

    print("Loading LAU polygons...")
    lau_gdf = load_lau(lau_file, target_countries=target_countries)
    print(f"Loaded {len(lau_gdf):,} LAU polygons after filtering.")

    print("Mapping points to LAU...")
    points_gdf = build_points_gdf(points_df, point_columns)
    points_with_lau = map_points_to_lau(points_gdf, lau_gdf)
    points_with_lau = attach_france_lookup(points_with_lau, france_lookup_file)
    points_with_lau["insee_com_key"] = normalize_insee_code_series(points_with_lau.get("insee_com"))

    target_insee_codes = {
        code
        for code in points_with_lau["insee_com_key"].dropna().astype(str).str.strip().tolist()
        if code
    }
    print(f"{len(target_insee_codes):,} unique current commune codes found under the supplied points.")

    print("Loading Gaspar commune events...")
    gaspar_events_df = load_resolved_gaspar_events(
        gaspar_file=gaspar_file,
        gaspar_sheet_name=args.gaspar_sheet_name,
        france_lookup_file=france_lookup_file,
        france_old_insee_updates_file=france_old_insee_updates_file,
        target_insee_codes=target_insee_codes,
    )
    gaspar_events_df = filter_records_by_global_interval(
        gaspar_events_df,
        event_start_col="gaspar_start_date",
        event_end_col="gaspar_end_date",
        study_start=args.study_start,
        study_end=args.study_end,
    )
    print(f"Loaded {len(gaspar_events_df):,} Gaspar commune-event rows after global filtering.")

    gaspar_candidate_df = build_gaspar_candidate_events(
        points_with_lau=points_with_lau,
        point_columns=point_columns,
        gaspar_events_df=gaspar_events_df,
        row_study_period_columns=row_study_period_columns,
    )

    print("Classifying points against TRI and riparian polygons...")
    tri_classification_df = classify_points_against_tri(
        points_gdf=points_gdf,
        point_columns=point_columns,
        tri_archive=tri_archive,
        riparian_root=riparian_root,
    )

    gaspar_candidate_sheet = build_gaspar_candidate_sheet(
        gaspar_candidate_df=gaspar_candidate_df.drop(columns="geometry", errors="ignore"),
        point_columns=point_columns,
        tri_classification_df=tri_classification_df,
        row_study_period_columns=row_study_period_columns,
    )
    gaspar_hits_sheet = build_gaspar_hits_sheet(gaspar_candidate_sheet)
    gaspar_hit_point_ids = (
        set(gaspar_hits_sheet["point_id"].dropna().tolist())
        if "point_id" in gaspar_hits_sheet.columns
        else set()
    )
    gaspar_point_flag_sheet = build_point_flag_sheet(
        points_df,
        point_columns.point_id,
        gaspar_hit_point_ids,
    )
    gaspar_detailed_sheet = build_detailed_sheet(
        points_df,
        point_columns.point_id,
        gaspar_hit_point_ids,
    )

    print("Writing Gaspar workbook...")
    write_gaspar_output_workbook(
        output_path=out_file,
        point_flag_sheet=gaspar_point_flag_sheet,
        detailed_sheet=gaspar_detailed_sheet,
        candidate_sheet=gaspar_candidate_sheet,
        hits_sheet=gaspar_hits_sheet,
    )

    print("Done.")
    print(f"Gaspar workbook: {out_file.resolve()}")
    print(
        {
            "n_points": int(len(points_df)),
            "n_gaspar_candidate_rows": int(len(gaspar_candidate_sheet)),
            "n_gaspar_event_hits": int(len(gaspar_hits_sheet)),
            "n_gaspar_points_flagged": int(gaspar_point_flag_sheet["flag_flood"].sum()),
            "row_study_columns_used": list(ROW_STUDY_PERIOD_OUTPUT_COLUMNS),
        }
    )


if __name__ == "__main__":
    main()
