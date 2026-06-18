from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from check_points_against_jrc_floods import (
    DEFAULT_EVENT_TABLE,
    DEFAULT_FLOOD_DIR,
    DEFAULT_LAU_FILE,
    DEFAULT_POINT_BUFFER_M,
    DEFAULT_SURROUNDING_BUFFER_KM,
    PointColumns,
    ROW_STUDY_PERIOD_OUTPUT_COLUMNS,
    RowStudyPeriodColumns,
    build_candidate_sheet,
    build_detailed_sheet,
    build_hits_sheet,
    build_point_flag_sheet,
    build_points_gdf,
    build_row_level_study_periods,
    filter_candidate_events_by_interval_columns,
    filter_candidate_events_by_row_study_period,
    filter_events_by_study_period,
    filter_records_by_global_interval,
    inspect_candidate_events,
    load_lau_events,
    load_points_table,
    map_points_to_lau,
    parse_date_series,
    point_ids_intersecting_polygons,
    resolve_raster_paths,
    transform_bbox_from_4326,
    write_output_workbook,
)
from granular_tabularization import load_lau


DEFAULT_ITALY_POINT_FILE = Path("data/processed/T20_Anonymised.xlsx")
DEFAULT_LAU_NUTS_LOOKUP = Path("data/processed/_outputs_eurostat_full/lau_nuts_lookup.csv")
DEFAULT_HANZE_FILE = Path("data/processed/HANZE_events_v3_transformed.csv")
DEFAULT_ITALY_TRI_ROOT = Path("data/raw/Mosaicatura_ISPRA_2020_aree_pericolosita_idraulica")
DEFAULT_JRC_OUTPUT = Path("data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx")
DEFAULT_HANZE_MIN_YEAR = 2000

LAU_NUTS_LOOKUP_COLUMNS = [
    "lau_code",
    "lau_code_local",
    "lau_name",
    "country_code",
    "country_name",
    "nuts0_code",
    "nuts0_name",
    "nuts1_code",
    "nuts1_name",
    "nuts2_code",
    "nuts2_name",
    "nuts3_code",
    "nuts3_name",
    "population_2024",
    "area_km2",
]

HANZE_REQUIRED_COLUMNS = [
    "ID",
    "Country code",
    "Year",
    "Country name",
    "Start date",
    "End date",
    "Type",
    "Flood source",
    "NUTS3",
    "NUTS3_name",
]

HANZE_EVENT_HITS_COLUMNS = [
    "point_id",
    "excel_row_number",
    "point_latitude",
    "point_longitude",
    "lau_code",
    "lau_name",
    "nuts3_code",
    "nuts3_name",
    "study_period_end",
    "study_period_end_source",
    "hanze_event_uid",
    "hanze_event_id",
    "hanze_start_date",
    "hanze_end_date",
    "hanze_country_code",
    "hanze_country_name",
    "hanze_event_type",
    "hanze_flood_source",
    "italy_tri_high_hazard_hit",
    "flood_risk_area_value",
    "hanze_spatial_hit",
    "hanze_hit_reason",
]

ITALY_TRI_HIGH_LAYER_PREFIX = "hph_"


def attach_lau_nuts_lookup(points_lau: pd.DataFrame, lookup_path: Path | None) -> pd.DataFrame:
    result = points_lau.copy()
    for column in LAU_NUTS_LOOKUP_COLUMNS[4:]:
        if column not in result.columns:
            result[column] = pd.NA

    if lookup_path is None or not lookup_path.exists():
        return result

    lookup_df = pd.read_csv(lookup_path)
    keep = [column for column in LAU_NUTS_LOOKUP_COLUMNS if column in lookup_df.columns]
    lookup_df = lookup_df[keep].drop_duplicates(subset=["lau_code"]).copy()
    drop_columns = [column for column in keep if column != "lau_code" and column in result.columns]
    result = result.drop(columns=drop_columns, errors="ignore")
    return result.merge(lookup_df, on="lau_code", how="left")


def load_hanze_events(
    hanze_file: Path,
    target_nuts3_codes: set[str],
    *,
    target_country_code: str,
    min_year: int,
) -> pd.DataFrame:
    if not target_nuts3_codes:
        return pd.DataFrame(
            columns=[
                "hanze_event_uid",
                "hanze_event_id",
                "hanze_country_code",
                "hanze_country_name",
                "hanze_start_date",
                "hanze_end_date",
                "hanze_event_type",
                "hanze_flood_source",
                "nuts3_code",
                "hanze_nuts3_name",
            ]
        )

    hanze_df = pd.read_csv(
        hanze_file,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
        encoding="utf-8-sig",
    )
    hanze_df.columns = [str(column).strip() for column in hanze_df.columns]

    missing_cols = [column for column in HANZE_REQUIRED_COLUMNS if column not in hanze_df.columns]
    if missing_cols:
        raise KeyError(f"Missing expected HANZE columns: {missing_cols}")

    hanze_df["Country code"] = hanze_df["Country code"].astype(str).str.strip().str.upper()
    hanze_df["NUTS3"] = hanze_df["NUTS3"].astype(str).str.strip()
    hanze_df = hanze_df[
        hanze_df["Country code"].eq(target_country_code.upper())
        & hanze_df["NUTS3"].isin(target_nuts3_codes)
    ].copy()

    if hanze_df.empty:
        return pd.DataFrame(
            columns=[
                "hanze_event_uid",
                "hanze_event_id",
                "hanze_country_code",
                "hanze_country_name",
                "hanze_start_date",
                "hanze_end_date",
                "hanze_event_type",
                "hanze_flood_source",
                "nuts3_code",
                "hanze_nuts3_name",
            ]
        )

    hanze_df["hanze_start_date"] = parse_date_series(hanze_df["Start date"])
    hanze_df["hanze_end_date"] = parse_date_series(hanze_df["End date"])
    hanze_df["hanze_start_date"] = hanze_df["hanze_start_date"].combine_first(hanze_df["hanze_end_date"])
    hanze_df["hanze_end_date"] = hanze_df["hanze_end_date"].combine_first(hanze_df["hanze_start_date"])
    hanze_df["hanze_year"] = pd.to_numeric(hanze_df["Year"], errors="coerce")
    hanze_df["hanze_year"] = (
        hanze_df["hanze_year"]
        .combine_first(hanze_df["hanze_start_date"].dt.year.astype("float"))
        .combine_first(hanze_df["hanze_end_date"].dt.year.astype("float"))
    )
    hanze_df = hanze_df[hanze_df["hanze_year"].ge(float(min_year), fill_value=False)].copy()

    hanze_df["hanze_event_id"] = hanze_df["ID"].astype(str).str.strip()
    hanze_df["nuts3_code"] = hanze_df["NUTS3"].astype(str).str.strip()
    hanze_df["hanze_event_uid"] = [
        f"{event_id}__{nuts3_code}__{index}"
        for index, (event_id, nuts3_code) in enumerate(
            zip(hanze_df["hanze_event_id"], hanze_df["nuts3_code"], strict=False),
            start=1,
        )
    ]
    hanze_df["hanze_country_code"] = hanze_df["Country code"].astype(str).str.strip()
    hanze_df["hanze_country_name"] = hanze_df["Country name"].astype(str).str.strip()
    hanze_df["hanze_event_type"] = hanze_df["Type"].astype(str).str.strip()
    hanze_df["hanze_flood_source"] = hanze_df["Flood source"].astype(str).str.strip()
    hanze_df["hanze_nuts3_name"] = hanze_df["NUTS3_name"].astype(str).str.strip()

    keep_columns = [
        "hanze_event_uid",
        "hanze_event_id",
        "hanze_country_code",
        "hanze_country_name",
        "hanze_start_date",
        "hanze_end_date",
        "hanze_event_type",
        "hanze_flood_source",
        "nuts3_code",
        "hanze_nuts3_name",
    ]
    return hanze_df[keep_columns].drop_duplicates(subset=["hanze_event_uid"]).reset_index(drop=True)


def build_point_base(
    points_with_lau: pd.DataFrame,
    point_columns: PointColumns,
    row_study_period_columns: RowStudyPeriodColumns | None,
) -> pd.DataFrame:
    point_base_columns = [
        point_columns.point_id,
        point_columns.latitude,
        point_columns.longitude,
        "excel_row_number",
        "geometry",
        "lau_code",
        "lau_code_local",
        "lau_name",
        "country_code",
        "population_2024",
        "area_km2",
        "nuts0_code",
        "nuts0_name",
        "nuts1_code",
        "nuts1_name",
        "nuts2_code",
        "nuts2_name",
        "nuts3_code",
        "nuts3_name",
    ]
    if point_columns.city and point_columns.city in points_with_lau.columns:
        point_base_columns.append(point_columns.city)
    if row_study_period_columns:
        for raw_col in [
            row_study_period_columns.anchor,
            row_study_period_columns.primary_end,
            row_study_period_columns.fallback_end,
        ]:
            if raw_col and raw_col in points_with_lau.columns and raw_col not in point_base_columns:
                point_base_columns.append(raw_col)
    for derived_col in ROW_STUDY_PERIOD_OUTPUT_COLUMNS:
        if derived_col in points_with_lau.columns and derived_col not in point_base_columns:
            point_base_columns.append(derived_col)
    available_columns = [column for column in point_base_columns if column in points_with_lau.columns]
    return points_with_lau[available_columns].copy()


def build_hanze_candidate_events(
    points_with_lau: pd.DataFrame,
    point_columns: PointColumns,
    hanze_events_df: pd.DataFrame,
    row_study_period_columns: RowStudyPeriodColumns | None,
) -> pd.DataFrame:
    if hanze_events_df.empty:
        return pd.DataFrame()

    point_base = build_point_base(points_with_lau, point_columns, row_study_period_columns)
    hanze_candidate_df = point_base.merge(
        hanze_events_df,
        on="nuts3_code",
        how="left",
    )
    return filter_candidate_events_by_interval_columns(
        hanze_candidate_df,
        start_col="study_period_start",
        end_col="study_period_end",
        event_start_col="hanze_start_date",
        event_end_col="hanze_end_date",
    )


def derive_hanze_output_path(output_path: Path) -> Path:
    stem = output_path.stem
    if "jrc_flood_check" in stem:
        hanze_stem = stem.replace("jrc_flood_check", "hanze_tri_check")
    else:
        hanze_stem = f"{stem}_hanze_tri_check"
    if hanze_stem == stem:
        hanze_stem = f"{stem}_hanze_tri_check"
    return output_path.with_name(f"{hanze_stem}{output_path.suffix}")


def is_italy_tri_high_member(member_name: str) -> bool:
    name = Path(member_name).name.lower()
    return name.startswith(ITALY_TRI_HIGH_LAYER_PREFIX) or "elevata" in name


def find_italy_tri_high_member(tri_root: Path) -> str | None:
    if tri_root.is_dir():
        for path in sorted(tri_root.rglob("*.shp")):
            if is_italy_tri_high_member(path.name):
                return path.relative_to(tri_root).as_posix()
        return None

    with zipfile.ZipFile(tri_root) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".shp") and is_italy_tri_high_member(name):
                return name
    return None


def italy_tri_member_uri(tri_root: Path, member_name: str) -> str:
    if tri_root.is_dir():
        return str((tri_root / Path(member_name)).resolve())
    return f"zip://{tri_root.resolve().as_posix()}!{member_name}"


def empty_italy_tri_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"geometry": [], "italy_tri_layer": []}, geometry="geometry", crs=4326)


def load_italy_tri_high_polygons(
    tri_root: Path,
    *,
    bbox: tuple[float, float, float, float] | None,
) -> gpd.GeoDataFrame:
    member_name = find_italy_tri_high_member(tri_root)
    if not member_name:
        return empty_italy_tri_gdf()

    member_uri = italy_tri_member_uri(tri_root, member_name)
    sample = gpd.read_file(member_uri, rows=1)
    sample_crs = sample.crs or "EPSG:4326"

    read_bbox = bbox
    if bbox is not None and str(sample_crs) != "EPSG:4326":
        read_bbox = transform_bbox_from_4326(bbox, sample_crs)

    tri_gdf = gpd.read_file(member_uri, bbox=read_bbox)
    if tri_gdf.empty:
        return empty_italy_tri_gdf()

    tri_gdf = tri_gdf[["geometry"]].copy()
    tri_gdf["italy_tri_layer"] = Path(member_name).name
    if tri_gdf.crs is None:
        tri_gdf = tri_gdf.set_crs(sample_crs)
    if str(tri_gdf.crs) != "EPSG:4326":
        tri_gdf = tri_gdf.to_crs(4326)
    return tri_gdf


def classify_points_against_italy_tri(
    points_gdf: gpd.GeoDataFrame,
    point_columns: PointColumns,
    italy_tri_root: Path,
) -> pd.DataFrame:
    point_id_col = point_columns.point_id
    if points_gdf.empty:
        return pd.DataFrame(
            columns=[
                point_id_col,
                "italy_tri_high_hazard_hit",
                "flood_risk_area_value",
            ]
        )

    if not italy_tri_root.exists():
        classification_df = points_gdf[[point_id_col]].drop_duplicates(subset=[point_id_col]).copy()
        classification_df["italy_tri_high_hazard_hit"] = False
        classification_df["flood_risk_area_value"] = "other"
        return classification_df

    bbox = tuple(points_gdf.total_bounds.tolist())
    tri_high_polygons = load_italy_tri_high_polygons(italy_tri_root, bbox=bbox)
    base_points = points_gdf[[point_id_col, "geometry"]].drop_duplicates(subset=[point_id_col]).copy()
    high_ids = point_ids_intersecting_polygons(base_points, point_id_col, tri_high_polygons)

    classification_df = base_points[[point_id_col]].copy()
    classification_df["italy_tri_high_hazard_hit"] = classification_df[point_id_col].isin(high_ids)
    classification_df["flood_risk_area_value"] = np.where(
        classification_df["italy_tri_high_hazard_hit"],
        "high",
        "other",
    )
    return classification_df


def build_hanze_candidate_sheet(
    hanze_candidate_df: pd.DataFrame,
    point_columns: PointColumns,
    tri_classification_df: pd.DataFrame,
    row_study_period_columns: RowStudyPeriodColumns | None = None,
) -> pd.DataFrame:
    expected_columns = [
        "point_id",
        "point_latitude",
        "point_longitude",
        "excel_row_number",
        "lau_code",
        "lau_name",
        "nuts3_code",
        "nuts3_name",
        "hanze_event_uid",
        "hanze_event_id",
        "hanze_start_date",
        "hanze_end_date",
        "hanze_country_code",
        "hanze_country_name",
        "hanze_event_type",
        "hanze_flood_source",
        "italy_tri_high_hazard_hit",
        "flood_risk_area_value",
        "hanze_spatial_hit",
        "hanze_hit_reason",
    ]
    if hanze_candidate_df.empty or "hanze_event_uid" not in hanze_candidate_df.columns:
        return pd.DataFrame(columns=expected_columns)

    hanze_only = hanze_candidate_df[hanze_candidate_df["hanze_event_uid"].notna()].copy()
    if hanze_only.empty:
        return pd.DataFrame(columns=expected_columns)

    point_id_col = point_columns.point_id
    hanze_only = hanze_only.rename(
        columns={
            point_id_col: "point_id",
            point_columns.latitude: "point_latitude",
            point_columns.longitude: "point_longitude",
        }
    )
    if point_columns.city and point_columns.city in hanze_only.columns:
        hanze_only = hanze_only.rename(columns={point_columns.city: "point_city"})

    tri_merge_columns = [point_id_col, "italy_tri_high_hazard_hit", "flood_risk_area_value"]
    tri_merge_columns = [column for column in tri_merge_columns if column in tri_classification_df.columns]
    if tri_merge_columns:
        hanze_only = hanze_only.merge(
            tri_classification_df[tri_merge_columns].drop_duplicates(subset=[point_id_col]).rename(
                columns={point_id_col: "point_id"}
            ),
            on="point_id",
            how="left",
        )

    if "italy_tri_high_hazard_hit" not in hanze_only.columns:
        hanze_only["italy_tri_high_hazard_hit"] = False
    hanze_only["italy_tri_high_hazard_hit"] = hanze_only["italy_tri_high_hazard_hit"].fillna(False).astype(bool)

    if "flood_risk_area_value" not in hanze_only.columns:
        hanze_only["flood_risk_area_value"] = "other"
    hanze_only["flood_risk_area_value"] = (
        hanze_only["flood_risk_area_value"].astype("string").fillna("other").str.lower()
    )

    hanze_only["hanze_spatial_hit"] = hanze_only["italy_tri_high_hazard_hit"].astype(bool)
    hanze_only["hanze_hit_reason"] = np.where(
        hanze_only["hanze_spatial_hit"],
        "hanze_and_tri_high",
        "hanze_without_tri_high",
    )

    preferred_order = [
        "point_id",
        "point_city",
        "excel_row_number",
        "point_latitude",
        "point_longitude",
        "lau_code",
        "lau_name",
        "nuts3_code",
        "nuts3_name",
        "hanze_event_uid",
        "hanze_event_id",
        "hanze_start_date",
        "hanze_end_date",
        "hanze_country_code",
        "hanze_country_name",
        "hanze_event_type",
        "hanze_flood_source",
        "italy_tri_high_hazard_hit",
        "flood_risk_area_value",
        "hanze_spatial_hit",
        "hanze_hit_reason",
    ]
    if row_study_period_columns:
        for raw_col in [
            row_study_period_columns.anchor,
            row_study_period_columns.primary_end,
            row_study_period_columns.fallback_end,
        ]:
            if raw_col and raw_col in hanze_only.columns and raw_col not in preferred_order:
                preferred_order.append(raw_col)
        for column in ROW_STUDY_PERIOD_OUTPUT_COLUMNS:
            if column in hanze_only.columns and column not in preferred_order:
                preferred_order.append(column)

    available_columns = [column for column in preferred_order if column in hanze_only.columns]
    sort_columns = [column for column in ["point_id", "hanze_start_date", "hanze_event_uid"] if column in hanze_only.columns]
    result = hanze_only[available_columns].copy()
    if sort_columns:
        result = result.sort_values(sort_columns)
    return result


def build_hanze_hits_sheet(hanze_candidate_sheet: pd.DataFrame) -> pd.DataFrame:
    if hanze_candidate_sheet.empty or "hanze_spatial_hit" not in hanze_candidate_sheet.columns:
        return hanze_candidate_sheet.copy()
    hits = hanze_candidate_sheet[hanze_candidate_sheet["hanze_spatial_hit"].fillna(False)].copy()
    available_columns = [column for column in HANZE_EVENT_HITS_COLUMNS if column in hits.columns]
    return hits[available_columns].copy()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check Italian point coordinates against processed JRC flood events and "
            "against HANZE plus Italy TRI high-hazard polygons."
        )
    )
    parser.add_argument("--points-file", default=str(DEFAULT_ITALY_POINT_FILE), help="Input Excel workbook with latitude and longitude columns.")
    parser.add_argument("--sheet-name", default=None, help="Optional sheet name. Default uses the first sheet.")
    parser.add_argument("--latitude-col", default="Latitude", help="Latitude column name or alias. Default: Latitude.")
    parser.add_argument("--longitude-col", default="Longitude", help="Longitude column name or alias. Default: Longitude.")
    parser.add_argument("--point-id-col", default="#", help="Point identifier column. Default: #.")
    parser.add_argument("--city-col", default="City", help="Optional point label column. Default: City.")
    parser.add_argument("--lau-file", default=str(DEFAULT_LAU_FILE), help="Path to the Eurostat LAU GeoPackage.")
    parser.add_argument("--lau-country-filter", default="IT", help="Optional country filter for the LAU layer. Default: IT.")
    parser.add_argument("--lau-nuts-lookup-file", default=str(DEFAULT_LAU_NUTS_LOOKUP), help="Lookup CSV used to attach NUTS fields to LAU codes.")
    parser.add_argument("--events-file", default=str(DEFAULT_EVENT_TABLE), help="Processed LAU event table (.parquet or .csv).")
    parser.add_argument("--flood-dir", default=str(DEFAULT_FLOOD_DIR), help="Root directory containing the official JRC flood TIFF folders.")
    parser.add_argument("--hanze-file", default=str(DEFAULT_HANZE_FILE), help="Expanded HANZE events CSV with one row per NUTS3 region.")
    parser.add_argument("--hanze-country-code", default="IT", help="HANZE country code filter. Default: IT.")
    parser.add_argument("--hanze-min-year", type=int, default=DEFAULT_HANZE_MIN_YEAR, help=f"Minimum HANZE event year kept by the Italy fallback branch. Default: {DEFAULT_HANZE_MIN_YEAR}.")
    parser.add_argument("--italy-tri-root", default=str(DEFAULT_ITALY_TRI_ROOT), help="Italy TRI root folder or zip archive. The script uses only the HPH/elevata polygons.")
    parser.add_argument("--study-start", default=None, help="Optional study-period start date (YYYY-MM-DD). Keeps only events whose intervals overlap this bound.")
    parser.add_argument("--study-end", default=None, help="Optional study-period end date (YYYY-MM-DD). Keeps only events whose intervals overlap this bound.")
    parser.add_argument("--row-study-anchor-col", default=None, help="Optional workbook column used as the per-row anchor date when a lookback window is requested.")
    parser.add_argument("--row-study-end-col", default=None, help="Optional workbook column used as the preferred per-row study-period end date.")
    parser.add_argument("--row-study-end-fallback-col", default=None, help="Optional fallback workbook column used when the preferred per-row end date is empty.")
    parser.add_argument("--row-study-lookback-years", type=int, default=None, help="Optional years to subtract from the per-row anchor date. Leave blank to keep the full history up to the row end date.")
    parser.add_argument("--point-buffer-m", type=float, default=DEFAULT_POINT_BUFFER_M, help=f"Radius in meters used for the local point match metrics. Default: {DEFAULT_POINT_BUFFER_M:.0f}.")
    parser.add_argument("--buffer-km", type=float, default=DEFAULT_SURROUNDING_BUFFER_KM, help=f"Radius in kilometers used for the surrounding buffer metrics. Default: {DEFAULT_SURROUNDING_BUFFER_KM:.1f}.")
    parser.add_argument("--threshold-cm", type=float, default=0.0, help="Minimum depth in cm to count as flooded. Default: 0.0.")
    parser.add_argument("--out-file", default=str(DEFAULT_JRC_OUTPUT), help="Output Excel workbook for the JRC branch.")
    parser.add_argument("--hanze-out-file", default=None, help="Optional HANZE plus TRI workbook. Default derives a sibling file next to --out-file using a _hanze_tri_check name.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    points_file = Path(args.points_file)
    lau_file = Path(args.lau_file)
    lau_nuts_lookup_file = Path(args.lau_nuts_lookup_file) if args.lau_nuts_lookup_file else None
    events_file = Path(args.events_file)
    flood_dir = Path(args.flood_dir)
    hanze_file = Path(args.hanze_file)
    italy_tri_root = Path(args.italy_tri_root)
    out_file = Path(args.out_file)
    hanze_out_file = Path(args.hanze_out_file) if args.hanze_out_file else derive_hanze_output_path(out_file)

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
    if row_study_period_columns:
        lookback_label = (
            f"lookback_years={args.row_study_lookback_years}"
            if args.row_study_lookback_years is not None
            else "lookback_years=full_history"
        )
        print(
            "Derived row-level study periods using "
            f"anchor={row_study_period_columns.anchor!r}, "
            f"end={row_study_period_columns.primary_end!r}, "
            f"fallback_end={row_study_period_columns.fallback_end!r}, "
            f"{lookback_label}."
        )

    print("Loading LAU polygons...")
    lau_gdf = load_lau(lau_file, target_countries=target_countries)
    print(f"Loaded {len(lau_gdf):,} LAU polygons after filtering.")

    print("Mapping points to LAU and attaching NUTS3...")
    points_gdf = build_points_gdf(points_df, point_columns)
    points_with_lau = map_points_to_lau(points_gdf, lau_gdf)
    points_with_lau = attach_lau_nuts_lookup(points_with_lau, lau_nuts_lookup_file)

    point_base = build_point_base(points_with_lau, point_columns, row_study_period_columns)

    target_lau_codes = {
        code
        for code in points_with_lau.get("lau_code", pd.Series(dtype="object")).dropna().astype(str).str.strip().tolist()
        if code
    }
    print(f"{len(target_lau_codes):,} unique LAU codes found under the supplied points.")

    print("Loading processed LAU event table for the JRC branch...")
    event_df = load_lau_events(events_file, target_lau_codes)
    event_df = filter_events_by_study_period(
        event_df,
        study_start=args.study_start,
        study_end=args.study_end,
    )
    print(f"Loaded {len(event_df):,} candidate LAU-event rows for the mapped points.")

    candidate_df_all = point_base.merge(event_df, on="lau_code", how="left", suffixes=("", "_event"))
    candidate_df = filter_candidate_events_by_row_study_period(candidate_df_all)
    candidate_df = resolve_raster_paths(candidate_df, flood_dir=flood_dir)

    print("Inspecting exact pixels and local buffers for JRC candidates...")
    inspected_df = inspect_candidate_events(
        candidate_df=candidate_df,
        point_columns=point_columns,
        point_buffer_m=args.point_buffer_m,
        surrounding_buffer_km=args.buffer_km,
        threshold_cm=args.threshold_cm,
    )

    jrc_candidate_sheet = build_candidate_sheet(
        candidate_df=pd.DataFrame(candidate_df.drop(columns="geometry", errors="ignore")),
        point_columns=point_columns,
        inspected_df=inspected_df,
        row_study_period_columns=row_study_period_columns,
    )
    jrc_hits_sheet = build_hits_sheet(jrc_candidate_sheet)
    jrc_hit_point_ids = set(jrc_hits_sheet.get("point_id", pd.Series(dtype="object")).dropna().tolist())
    jrc_point_flag_sheet = build_point_flag_sheet(
        points_df,
        point_columns.point_id,
        jrc_hit_point_ids,
    )
    jrc_detailed_sheet = build_detailed_sheet(
        points_df,
        point_columns.point_id,
        jrc_hit_point_ids,
    )

    target_nuts3_codes = {
        code
        for code in points_with_lau.get("nuts3_code", pd.Series(dtype="object")).dropna().astype(str).str.strip().tolist()
        if code
    }
    print("Loading HANZE events for the Italy fallback branch...")
    hanze_events_df = load_hanze_events(
        hanze_file,
        target_nuts3_codes=target_nuts3_codes,
        target_country_code=args.hanze_country_code,
        min_year=args.hanze_min_year,
    )
    hanze_events_df = filter_records_by_global_interval(
        hanze_events_df,
        event_start_col="hanze_start_date",
        event_end_col="hanze_end_date",
        study_start=args.study_start,
        study_end=args.study_end,
    )
    print(
        f"Loaded {len(hanze_events_df):,} HANZE candidate rows after the country, "
        f"NUTS3, min-year>={args.hanze_min_year}, and date filters."
    )

    print("Classifying points against Italy TRI high-hazard polygons...")
    tri_classification_df = classify_points_against_italy_tri(
        points_gdf=points_gdf,
        point_columns=point_columns,
        italy_tri_root=italy_tri_root,
    )

    hanze_candidate_df = build_hanze_candidate_events(
        points_with_lau=points_with_lau,
        point_columns=point_columns,
        hanze_events_df=hanze_events_df,
        row_study_period_columns=row_study_period_columns,
    )
    hanze_candidate_sheet = build_hanze_candidate_sheet(
        hanze_candidate_df=pd.DataFrame(hanze_candidate_df.drop(columns="geometry", errors="ignore")),
        point_columns=point_columns,
        tri_classification_df=tri_classification_df,
        row_study_period_columns=row_study_period_columns,
    )
    hanze_hits_sheet = build_hanze_hits_sheet(hanze_candidate_sheet)
    hanze_hit_point_ids = set(hanze_hits_sheet.get("point_id", pd.Series(dtype="object")).dropna().tolist())
    hanze_point_flag_sheet = build_point_flag_sheet(
        points_df,
        point_columns.point_id,
        hanze_hit_point_ids,
    )
    hanze_detailed_sheet = build_detailed_sheet(
        points_df,
        point_columns.point_id,
        hanze_hit_point_ids,
    )

    print("Writing JRC workbook...")
    write_output_workbook(
        output_path=out_file,
        point_flag_sheet=jrc_point_flag_sheet,
        detailed_sheet=jrc_detailed_sheet,
        candidate_sheet=jrc_candidate_sheet,
        hits_sheet=jrc_hits_sheet,
    )
    print("Writing HANZE plus TRI workbook...")
    write_output_workbook(
        output_path=hanze_out_file,
        point_flag_sheet=hanze_point_flag_sheet,
        detailed_sheet=hanze_detailed_sheet,
        candidate_sheet=hanze_candidate_sheet,
        hits_sheet=hanze_hits_sheet,
    )

    print("Done.")
    print(f"JRC workbook: {out_file.resolve()}")
    print(f"HANZE plus TRI workbook: {hanze_out_file.resolve()}")
    print(
        {
            "n_points": int(len(points_df)),
            "n_jrc_points_flagged": int(jrc_point_flag_sheet["flag_flood"].sum()),
            "n_jrc_candidate_rows": int(len(jrc_candidate_sheet)),
            "n_jrc_event_hits": int(len(jrc_hits_sheet)),
            "n_hanze_points_flagged": int(hanze_point_flag_sheet["flag_flood"].sum()),
            "n_hanze_candidate_rows": int(len(hanze_candidate_sheet)),
            "n_hanze_event_hits": int(len(hanze_hits_sheet)),
        }
    )


if __name__ == "__main__":
    main()
