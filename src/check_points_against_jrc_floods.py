from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.errors import WindowError
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import Point, box, mapping

from compare_france_jrc_gaspar_flexible import normalize_insee_code_series
from france_commune_activity import (
    DEFAULT_GASPAR_SHEET,
    load_france_lookup as load_france_activity_lookup,
    load_historical_insee_updates,
    prepare_processed_gaspar_rows,
    resolve_gaspar_current_communes,
)
from granular_tabularization import load_lau


PERMANENT_WATER_VALUE = 9999
DEFAULT_FRANCE_POINT_FILE = Path("data/raw/france_20_gps_google_maps.xlsx")
DEFAULT_EVENT_TABLE = Path("data/processed/_outputs_eurostat_full/events_lau_long.parquet")
DEFAULT_LAU_FILE = Path("data/raw/LAU_RG_01M_2024_4326.gpkg")
DEFAULT_FLOOD_DIR = Path("data/JRC_flood_depth_maps")
DEFAULT_FRANCE_LOOKUP = Path("data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv")
DEFAULT_FRANCE_OLD_INSEE_UPDATES = (
    Path("data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv")
)
DEFAULT_GASPAR_FILE = Path("data/processed/Gaspar_2015_2024.xlsx")
DEFAULT_TRI_ARCHIVE = Path("data/raw/tri_2020_sig_di")
DEFAULT_RIPARIAN_ROOT = Path("data/raw/France_Riparian")
DEFAULT_OUTPUT = Path("data/processed/france_points_jrc_flood_check.xlsx")
DEFAULT_POINT_BUFFER_M = 40.0
DEFAULT_SURROUNDING_BUFFER_KM = 1.0
TRI_ARCHIVE_ROOT = "tri_2020_sig_di"
TRI_INONDABLE_PREFIX = "n_inondable_"
TRI_BOUNDARY_FILENAME = "n_tri_s.shp"
TRI_SCENARIO_METADATA: dict[str, dict[str, str]] = {
    "01for": {
        "canonical_code": "01For",
        "tri_level": "high",
        "scenario_label": "Aléa de forte probabilité",
        "source_document": "COVADIS Directive inondation v2.0",
    },
    "01forcc_ct": {
        "canonical_code": "01Forcc_ct",
        "tri_level": "high",
        "scenario_label": "Aléa de forte probabilité avec prise en compte du changement climatique à court terme",
        "source_document": "Rapportage 2020 ArcGIS coded values",
    },
    "01forcc_100": {
        "canonical_code": "01Forcc_100",
        "tri_level": "high",
        "scenario_label": "Aléa de forte probabilité avec prise en compte du changement climatique à échéance 100 ans",
        "source_document": "Rapportage 2020 ArcGIS coded values",
    },
    "02moy": {
        "canonical_code": "02Moy",
        "tri_level": "medium",
        "scenario_label": "Aléa de moyenne probabilité",
        "source_document": "COVADIS Directive inondation v2.0",
    },
    "03mcc": {
        "canonical_code": "03Mcc",
        "tri_level": "medium",
        "scenario_label": "Aléa de moyenne probabilité avec prise en compte du changement climatique",
        "source_document": "COVADIS Directive inondation v2.0",
    },
    "03mcc_ct": {
        "canonical_code": "03Mcc_ct",
        "tri_level": "medium",
        "scenario_label": "Aléa de moyenne probabilité avec prise en compte du changement climatique à court terme",
        "source_document": "Rapportage 2020 ArcGIS coded values",
    },
    "04fai": {
        "canonical_code": "04Fai",
        "tri_level": "low",
        "scenario_label": "Aléa de faible probabilité",
        "source_document": "COVADIS Directive inondation v2.0",
    },
    "04faicc_ct": {
        "canonical_code": "04Faicc_ct",
        "tri_level": "low",
        "scenario_label": "Aléa de faible probabilité avec prise en compte du changement climatique à court terme",
        "source_document": "Rapportage 2020 ArcGIS coded values",
    },
    "04fai_100": {
        "canonical_code": "04Fai_100",
        "tri_level": "low",
        "scenario_label": "Aléa de faible probabilité avec prise en compte du changement climatique à échéance 100 ans",
        "source_document": "Rapportage 2020 ArcGIS coded values",
    },
}
TRI_LEVEL_PRIORITY = {
    "high": 0,
    "medium": 1,
    "low": 2,
    "out": 3,
}

EVENT_COLUMNS = [
    "event_id",
    "raster_file",
    "raster_path",
    "source_year_folder",
    "start_date",
    "end_date",
    "duration_days",
    "flood_id",
    "gfm_extent_km2",
    "enhanced_extent_km2",
    "centroid_lat_cents",
    "centroid_lon_cents",
    "spatial_spread_units",
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
    "max_depth_cm",
    "flooded_pixels",
    "flooded_area_m2",
]

LATITUDE_ALIASES = ("Latitude", "Lat", "Y")
LONGITUDE_ALIASES = ("Longitude", "Long", "Lon", "Lng", "X")
ROW_STUDY_PERIOD_OUTPUT_COLUMNS = [
    "study_period_anchor_date",
    "study_period_primary_end_date",
    "study_period_fallback_end_date",
    "study_period_start",
    "study_period_end",
    "study_period_end_source",
]

JRC_EVENT_HITS_COLUMNS = [
    "point_id",
    "excel_row_number",
    "point_latitude",
    "point_longitude",
    "lau_code",
    "lau_name",
    "insee_com",
    "Reference_Date",
    "Closed_Default_Date",
    "Cut_off_Date",
    "study_period_end",
    "study_period_end_source",
    "event_id",
    "raster_file",
    "start_date",
    "end_date",
    "duration_days",
    "max_depth_cm",
    "flooded_pixels",
    "flooded_area_m2",
    "hit_at_point",
    "exact_point_depth_cm",
    "point_buffer_radius_m",
    "point_buffer_flood_hit",
    "point_buffer_flooded_pixels",
    "point_buffer_flooded_pixel_pct",
    "point_buffer_flooded_area_m2",
    "point_buffer_min_depth_cm",
    "point_buffer_max_depth_cm",
    "point_buffer_median_depth_cm",
    "point_buffer_mean_depth_cm",
    "buffer_radius_km",
    "buffer_flood_hit",
    "buffer_flooded_pixels",
    "buffer_flooded_pixel_pct",
    "buffer_flooded_area_m2",
    "buffer_min_depth_cm",
    "buffer_max_depth_cm",
    "buffer_median_depth_cm",
    "buffer_mean_depth_cm",
]

GASPAR_EVENT_HITS_COLUMNS = [
    "point_id",
    "excel_row_number",
    "point_latitude",
    "point_longitude",
    "lau_code",
    "lau_name",
    "insee_com",
    "Reference_Date",
    "Closed_Default_Date",
    "Cut_off_Date",
    "study_period_end",
    "study_period_end_source",
    "gaspar_event_uid",
    "cod_nat_catnat",
    "gaspar_start_date",
    "gaspar_end_date",
    "gaspar_commune_name",
    "gaspar_commune_match_method",
    "tri_for_hit",
    "tri_boundary_hit",
    "tri_zone_status",
    "riparian_hit",
    "gaspar_hit_reason",
]

FRANCE_LOOKUP_COLUMNS = [
    "lau_code",
    "insee_com",
    "commune_name_adminexpress",
    "insee_dep",
    "insee_reg",
    "nuts3_code",
    "nuts3_name",
]


@dataclass(frozen=True)
class PointColumns:
    latitude: str
    longitude: str
    point_id: str
    city: str | None


@dataclass(frozen=True)
class RowStudyPeriodColumns:
    anchor: str | None
    primary_end: str | None
    fallback_end: str | None


def normalize_label(value: Any) -> str:
    if pd.isna(value):
        return ""
    return "".join(ch.lower() for ch in str(value).strip() if ch.isalnum() or ch == "#")


def has_any_normalized_label(labels: set[str], aliases: Iterable[str]) -> bool:
    return any(normalize_label(alias) in labels for alias in aliases)


def empty_datetime_series(index: pd.Index) -> pd.Series:
    return pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")


def resolve_optional_named_column(df: pd.DataFrame, requested: str | None, aliases: Iterable[str]) -> str | None:
    if not requested:
        return None
    return resolve_named_column(df, requested, aliases)


def normalize_decimal_text(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip().replace("\u00A0", "").replace(" ", "")
    if not text:
        return None

    last_comma = text.rfind(",")
    last_dot = text.rfind(".")
    if last_comma >= 0 and last_dot >= 0:
        if last_comma > last_dot:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return text


def parse_coordinate_series(series: pd.Series) -> pd.Series:
    direct_numeric = pd.to_numeric(series, errors="coerce")
    normalized_text = series.map(normalize_decimal_text)
    normalized_numeric = pd.to_numeric(normalized_text, errors="coerce")
    return direct_numeric.combine_first(normalized_numeric)


def detect_header_row(
    workbook_path: Path,
    sheet_name: str | int | None,
    max_scan_rows: int = 25,
) -> int:
    preview = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, nrows=max_scan_rows)
    if isinstance(preview, dict):
        if not preview:
            raise ValueError(f"No sheets found in workbook: {workbook_path}")
        preview = next(iter(preview.values()))
    for idx, row in preview.iterrows():
        labels = {normalize_label(value) for value in row.tolist() if normalize_label(value)}
        if has_any_normalized_label(labels, LATITUDE_ALIASES) and has_any_normalized_label(labels, LONGITUDE_ALIASES):
            return int(idx)
    return 0


def resolve_named_column(df: pd.DataFrame, requested: str | None, aliases: Iterable[str]) -> str:
    normalized_to_original = {
        normalize_label(column): str(column)
        for column in df.columns
        if normalize_label(column)
    }
    if requested:
        requested_norm = normalize_label(requested)
        if requested_norm in normalized_to_original:
            return normalized_to_original[requested_norm]
    for alias in aliases:
        alias_norm = normalize_label(alias)
        if alias_norm in normalized_to_original:
            return normalized_to_original[alias_norm]
    raise KeyError(f"Could not resolve any of the expected columns: {list(aliases)}")


def load_points_table(
    workbook_path: Path,
    sheet_name: str | int | None,
    latitude_col: str | None,
    longitude_col: str | None,
    point_id_col: str | None,
    city_col: str | None,
) -> tuple[pd.DataFrame, PointColumns]:
    header_row = detect_header_row(workbook_path, sheet_name)
    df = pd.read_excel(workbook_path, sheet_name=sheet_name, header=header_row)
    if isinstance(df, dict):
        if not df:
            raise ValueError(f"No sheets found in workbook: {workbook_path}")
        df = next(iter(df.values()))
    df = df.dropna(how="all").copy()
    df.columns = [str(col).strip() for col in df.columns]
    df["excel_row_number"] = np.arange(len(df)) + header_row + 2

    latitude_name = resolve_named_column(df, latitude_col, LATITUDE_ALIASES)
    longitude_name = resolve_named_column(df, longitude_col, LONGITUDE_ALIASES)
    try:
        point_id_name = resolve_named_column(df, point_id_col, ["#", "id", "point_id"])
    except KeyError:
        point_id_name = "point_id"
    city_name = None
    try:
        city_name = resolve_named_column(df, city_col, ["City", "Commune", "Address", "Location"])
    except KeyError:
        city_name = None

    if point_id_name not in df.columns:
        df[point_id_name] = np.arange(1, len(df) + 1)

    df[latitude_name] = parse_coordinate_series(df[latitude_name])
    df[longitude_name] = parse_coordinate_series(df[longitude_name])
    df = df[df[latitude_name].notna() & df[longitude_name].notna()].copy()

    return df, PointColumns(
        latitude=latitude_name,
        longitude=longitude_name,
        point_id=point_id_name,
        city=city_name,
    )


def parse_date_series(series: pd.Series, dayfirst: bool = True) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    if pd.api.types.is_numeric_dtype(series):
        numeric_values = pd.to_numeric(series, errors="coerce")
        return pd.Timestamp("1899-12-30") + pd.to_timedelta(numeric_values, unit="D")

    text = series.astype("string").str.strip()
    text = text.replace({"": pd.NA, "nan": pd.NA, "NaT": pd.NA, "None": pd.NA})
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)

    numeric_values = pd.to_numeric(text, errors="coerce")
    numeric_mask = parsed.isna() & numeric_values.notna()
    if numeric_mask.any():
        parsed = parsed.copy()
        parsed.loc[numeric_mask] = pd.Timestamp("1899-12-30") + pd.to_timedelta(
            numeric_values.loc[numeric_mask],
            unit="D",
        )
    return parsed


def build_row_level_study_periods(
    points_df: pd.DataFrame,
    anchor_col: str | None,
    end_col: str | None,
    fallback_end_col: str | None,
    lookback_years: int | None,
) -> tuple[pd.DataFrame, RowStudyPeriodColumns | None]:
    """Add per-row study windows used to filter candidate JRC events.

    For the T20 portfolio, the intended rule is:
    - start = full history by default, or Reference_Date minus X years when requested
    - end = Closed_Default_Date
    - fallback end = Cut_off_Date when Closed_Default_Date is empty
    """
    if not any([anchor_col, end_col, fallback_end_col]):
        return points_df, None
    if lookback_years is not None and lookback_years < 0:
        raise ValueError("--row-study-lookback-years must be 0 or greater.")

    result = points_df.copy()
    resolved_anchor = resolve_optional_named_column(
        result,
        anchor_col,
        [anchor_col, "Reference_Date", "Reference Date"],
    )
    resolved_end = resolve_optional_named_column(
        result,
        end_col,
        [end_col, "Closed_Default_Date", "Closed Default Date"],
    )
    resolved_fallback_end = resolve_optional_named_column(
        result,
        fallback_end_col,
        [fallback_end_col, "Cut_off_Date", "Cut off Date"],
    )

    anchor_dates = (
        parse_date_series(result[resolved_anchor])
        if resolved_anchor
        else empty_datetime_series(result.index)
    )
    primary_end_dates = (
        parse_date_series(result[resolved_end])
        if resolved_end
        else empty_datetime_series(result.index)
    )
    fallback_end_dates = (
        parse_date_series(result[resolved_fallback_end])
        if resolved_fallback_end
        else empty_datetime_series(result.index)
    )

    study_end = primary_end_dates.combine_first(fallback_end_dates)
    study_end_source = pd.Series(pd.NA, index=result.index, dtype="object")
    if resolved_end:
        study_end_source.loc[primary_end_dates.notna()] = resolved_end
    if resolved_fallback_end:
        fallback_mask = primary_end_dates.isna() & fallback_end_dates.notna()
        study_end_source.loc[fallback_mask] = resolved_fallback_end

    result["study_period_anchor_date"] = anchor_dates
    result["study_period_primary_end_date"] = primary_end_dates
    result["study_period_fallback_end_date"] = fallback_end_dates
    if lookback_years is None:
        result["study_period_start"] = pd.NaT
    else:
        result["study_period_start"] = anchor_dates - pd.DateOffset(years=lookback_years)
    result["study_period_end"] = study_end
    result["study_period_end_source"] = study_end_source

    return result, RowStudyPeriodColumns(
        anchor=resolved_anchor,
        primary_end=resolved_end,
        fallback_end=resolved_fallback_end,
    )


def build_points_gdf(points_df: pd.DataFrame, columns: PointColumns) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        points_df.copy(),
        geometry=gpd.points_from_xy(points_df[columns.longitude], points_df[columns.latitude]),
        crs=4326,
    )


def map_points_to_lau(points_gdf: gpd.GeoDataFrame, lau_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    lau_keep = [
        "lau_code",
        "lau_code_local",
        "lau_name",
        "country_code",
        "geometry",
    ]
    if "population_2024" in lau_gdf.columns:
        lau_keep.append("population_2024")
    if "area_km2" in lau_gdf.columns:
        lau_keep.append("area_km2")

    joined = gpd.sjoin(
        points_gdf,
        lau_gdf[lau_keep],
        how="left",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")

    missing = joined["lau_code"].isna()
    if missing.any():
        fallback = gpd.sjoin(
            points_gdf.loc[missing],
            lau_gdf[lau_keep],
            how="left",
            predicate="intersects",
        ).drop(columns=["index_right"], errors="ignore")
        fallback = fallback[~fallback.index.duplicated(keep="first")]
        for column in [col for col in lau_keep if col != "geometry"]:
            joined.loc[fallback.index, column] = fallback[column]

    joined = joined[~joined.index.duplicated(keep="first")].copy()
    return joined


def attach_france_lookup(points_lau: pd.DataFrame, lookup_path: Path | None) -> pd.DataFrame:
    result = points_lau.copy()
    for column in FRANCE_LOOKUP_COLUMNS[1:]:
        if column not in result.columns:
            result[column] = pd.NA

    if lookup_path is None or not lookup_path.exists():
        return result

    lookup_df = pd.read_csv(lookup_path)
    keep = [column for column in FRANCE_LOOKUP_COLUMNS if column in lookup_df.columns]
    lookup_df = lookup_df[keep].drop_duplicates(subset=["lau_code"]).copy()
    result = result.drop(columns=[col for col in keep if col != "lau_code" and col in result.columns], errors="ignore")
    result = result.merge(lookup_df, on="lau_code", how="left")
    return result


def load_lau_events(events_path: Path, target_lau_codes: set[str]) -> pd.DataFrame:
    if events_path.suffix.lower() == ".parquet":
        try:
            event_df = pd.read_parquet(events_path)
        except ImportError as exc:
            raise ImportError(
                "Reading the parquet event table requires pyarrow or fastparquet. "
                "Install the packages from requirements-pip.txt."
            ) from exc
    else:
        event_df = pd.read_csv(events_path)

    missing_cols = [column for column in EVENT_COLUMNS if column not in event_df.columns]
    if missing_cols:
        raise KeyError(f"Missing expected event-table columns: {missing_cols}")

    event_df = event_df[EVENT_COLUMNS].copy()
    event_df = event_df[event_df["lau_code"].isin(target_lau_codes)].copy()
    event_df["start_date"] = pd.to_datetime(event_df["start_date"], errors="coerce")
    event_df["end_date"] = pd.to_datetime(event_df["end_date"], errors="coerce")
    event_df = event_df.drop_duplicates(subset=["event_id", "lau_code"])
    return event_df


def filter_events_by_study_period(
    event_df: pd.DataFrame,
    study_start: str | None,
    study_end: str | None,
) -> pd.DataFrame:
    if event_df.empty or (not study_start and not study_end):
        return event_df

    result = event_df.copy()
    start_ts = pd.to_datetime(study_start, errors="coerce") if study_start else pd.NaT
    end_ts = pd.to_datetime(study_end, errors="coerce") if study_end else pd.NaT

    if study_start and pd.isna(start_ts):
        raise ValueError(f"Could not parse --study-start value: {study_start}")
    if study_end and pd.isna(end_ts):
        raise ValueError(f"Could not parse --study-end value: {study_end}")
    if pd.notna(start_ts):
        result = result[result["end_date"] >= start_ts].copy()
    if pd.notna(end_ts):
        result = result[result["start_date"] <= end_ts].copy()
    return result


def filter_candidate_events_by_row_study_period(candidate_df: pd.DataFrame) -> pd.DataFrame:
    """Keep only JRC events whose date interval overlaps each row's study window."""
    return filter_candidate_events_by_interval_columns(
        candidate_df,
        start_col="study_period_start",
        end_col="study_period_end",
    )


def filter_candidate_events_by_interval_columns(
    candidate_df: pd.DataFrame,
    start_col: str | None,
    end_col: str | None,
    *,
    event_start_col: str = "start_date",
    event_end_col: str = "end_date",
) -> pd.DataFrame:
    """Keep only candidate events whose date interval overlaps the supplied row-level interval columns."""
    if candidate_df.empty:
        return candidate_df
    if (not start_col or start_col not in candidate_df.columns) and (not end_col or end_col not in candidate_df.columns):
        return candidate_df

    result = candidate_df.copy()
    overlap_mask = pd.Series(True, index=result.index)

    # A candidate event is kept when the event interval [start_date, end_date]
    # overlaps the chosen row-specific study interval [start_col, end_col].
    if start_col and start_col in result.columns:
        overlap_mask &= result[start_col].isna() | result[event_end_col].ge(result[start_col])
    if end_col and end_col in result.columns:
        overlap_mask &= result[end_col].isna() | result[event_start_col].le(result[end_col])

    event_missing_mask = result[event_start_col].isna() & result[event_end_col].isna()
    keep_mask = event_missing_mask | overlap_mask.fillna(False)
    return result[keep_mask].copy()


def filter_records_by_global_interval(
    df: pd.DataFrame,
    *,
    event_start_col: str,
    event_end_col: str,
    study_start: str | None,
    study_end: str | None,
) -> pd.DataFrame:
    if df.empty or (not study_start and not study_end):
        return df

    result = df.copy()
    start_ts = pd.to_datetime(study_start, errors="coerce") if study_start else pd.NaT
    end_ts = pd.to_datetime(study_end, errors="coerce") if study_end else pd.NaT

    if study_start and pd.isna(start_ts):
        raise ValueError(f"Could not parse study start value: {study_start}")
    if study_end and pd.isna(end_ts):
        raise ValueError(f"Could not parse study end value: {study_end}")
    if pd.notna(start_ts):
        result = result[result[event_end_col] >= start_ts].copy()
    if pd.notna(end_ts):
        result = result[result[event_start_col] <= end_ts].copy()
    return result


def load_resolved_gaspar_events(
    gaspar_file: Path,
    gaspar_sheet_name: str | int,
    france_lookup_file: Path,
    france_old_insee_updates_file: Path,
    target_insee_codes: set[str],
) -> pd.DataFrame:
    gaspar_df, _ = prepare_processed_gaspar_rows(gaspar_file, sheet_name=gaspar_sheet_name)
    france_lookup_df = load_france_activity_lookup(france_lookup_file)
    historical_updates_df = load_historical_insee_updates(france_old_insee_updates_file)
    resolved_gaspar_df, _ = resolve_gaspar_current_communes(
        gaspar_df,
        france_lookup=france_lookup_df,
        historical_updates=historical_updates_df,
    )

    resolved_gaspar_df = resolved_gaspar_df[
        resolved_gaspar_df["gaspar_commune_match_found"].fillna(False)
    ].copy()
    resolved_gaspar_df["insee_com_key"] = normalize_insee_code_series(resolved_gaspar_df["insee_com"])
    resolved_gaspar_df = resolved_gaspar_df[resolved_gaspar_df["insee_com_key"].isin(target_insee_codes)].copy()

    keep_cols = [
        "gaspar_event_uid",
        "cod_nat_catnat",
        "num_risque_jo",
        "lib_risque_jo",
        "gaspar_start_date",
        "gaspar_end_date",
        "gaspar_source_cod_commune",
        "gaspar_source_insee_com",
        "gaspar_commune_name",
        "insee_com_key",
        "commune_name_current",
        "lau_code",
        "lau_code_local",
        "nuts3_code",
        "nuts3_name",
        "insee_dep",
        "insee_reg",
        "gaspar_commune_match_method",
    ]
    keep_cols = [column for column in keep_cols if column in resolved_gaspar_df.columns]
    resolved_gaspar_df = resolved_gaspar_df[keep_cols].copy()
    resolved_gaspar_df = resolved_gaspar_df.drop_duplicates(
        subset=["gaspar_event_uid", "insee_com_key"],
        keep="first",
    )
    return resolved_gaspar_df.reset_index(drop=True)


def build_gaspar_candidate_events(
    points_with_lau: pd.DataFrame,
    point_columns: PointColumns,
    gaspar_events_df: pd.DataFrame,
    row_study_period_columns: RowStudyPeriodColumns | None,
) -> pd.DataFrame:
    if gaspar_events_df.empty:
        return pd.DataFrame()

    point_key_cols = [
        point_columns.point_id,
        point_columns.latitude,
        point_columns.longitude,
        "excel_row_number",
        "lau_code",
        "lau_code_local",
        "lau_name",
        "country_code",
        "insee_com",
        "insee_dep",
        "insee_reg",
        "nuts3_code",
        "nuts3_name",
        "insee_com_key",
    ]
    if point_columns.city and point_columns.city in points_with_lau.columns:
        point_key_cols.append(point_columns.city)
    if row_study_period_columns:
        for raw_col in [
            row_study_period_columns.anchor,
            row_study_period_columns.primary_end,
            row_study_period_columns.fallback_end,
        ]:
            if raw_col and raw_col in points_with_lau.columns and raw_col not in point_key_cols:
                point_key_cols.append(raw_col)
    for derived_col in ROW_STUDY_PERIOD_OUTPUT_COLUMNS:
        if derived_col in points_with_lau.columns and derived_col not in point_key_cols:
            point_key_cols.append(derived_col)

    point_base = points_with_lau[point_key_cols].copy()
    gaspar_candidate_df = point_base.merge(
        gaspar_events_df,
        on="insee_com_key",
        how="left",
        suffixes=("", "_gaspar"),
    )
    return filter_candidate_events_by_interval_columns(
        gaspar_candidate_df,
        start_col="study_period_start",
        end_col="study_period_end",
        event_start_col="gaspar_start_date",
        event_end_col="gaspar_end_date",
    )


def normalize_tri_scenario_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower().replace(" ", "")


def extract_tri_scenario_key_from_member(member_name: str) -> str:
    stem = Path(member_name).stem.lower()
    if not stem.startswith(TRI_INONDABLE_PREFIX):
        return ""
    remainder = stem[len(TRI_INONDABLE_PREFIX) :]
    if "_" not in remainder:
        return ""
    _, scenario_part = remainder.split("_", 1)
    if scenario_part.endswith("_s"):
        scenario_part = scenario_part[:-2]
    return normalize_tri_scenario_key(scenario_part)


def tri_metadata_for_scenario_key(scenario_key: str) -> dict[str, str]:
    normalized_key = normalize_tri_scenario_key(scenario_key)
    metadata = TRI_SCENARIO_METADATA.get(normalized_key)
    if metadata is not None:
        return metadata
    canonical_code = str(scenario_key).strip() if str(scenario_key).strip() else "unknown"
    return {
        "canonical_code": canonical_code,
        "tri_level": "out",
        "scenario_label": f"Unmapped TRI scenario ({canonical_code})",
        "source_document": "unmapped",
    }


def classify_tri_level_from_scenario_keys(scenario_keys: Iterable[str]) -> str:
    levels = {
        tri_metadata_for_scenario_key(scenario_key)["tri_level"]
        for scenario_key in scenario_keys
        if normalize_tri_scenario_key(scenario_key)
    }
    if not levels:
        return "out"
    return min(levels, key=lambda level: TRI_LEVEL_PRIORITY.get(level, 999))


def list_tri_inondable_members(tri_archive: Path) -> list[tuple[str, str]]:
    shapefile_members: list[tuple[str, str]] = []
    if tri_archive.is_dir():
        for path in sorted(tri_archive.rglob("*.shp")):
            if not path.name.lower().startswith(TRI_INONDABLE_PREFIX):
                continue
            relative_name = path.relative_to(tri_archive).as_posix()
            scenario_key = extract_tri_scenario_key_from_member(path.name)
            shapefile_members.append((relative_name, scenario_key))
        return shapefile_members

    with zipfile.ZipFile(tri_archive) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".shp"):
                continue
            if not Path(name).name.lower().startswith(TRI_INONDABLE_PREFIX):
                continue
            scenario_key = extract_tri_scenario_key_from_member(Path(name).name)
            shapefile_members.append((name, scenario_key))
    return shapefile_members


def list_tri_for_members(tri_archive: Path) -> list[tuple[str, str]]:
    return [
        member_spec
        for member_spec in list_tri_inondable_members(tri_archive)
        if member_spec[1] == "01for"
    ]


def find_tri_member_by_filename(tri_archive: Path, filename: str) -> str | None:
    target_name = filename.lower()
    if tri_archive.is_dir():
        for path in sorted(tri_archive.rglob("*.shp")):
            if path.name.lower() == target_name:
                return path.relative_to(tri_archive).as_posix()
        return None

    with zipfile.ZipFile(tri_archive) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".shp") and Path(name).name.lower() == target_name:
                return name
    return None


def tri_member_uri(tri_archive: Path, member_name: str) -> str:
    if tri_archive.is_dir():
        return str((tri_archive / Path(member_name)).resolve())
    return f"zip://{tri_archive.resolve().as_posix()}!{member_name}"


def load_tri_polygon_members(
    tri_archive: Path,
    member_specs: Iterable[tuple[str, str]],
    *,
    bbox: tuple[float, float, float, float] | None,
) -> gpd.GeoDataFrame:
    frames: list[gpd.GeoDataFrame] = []
    for member_name, scenario_key in member_specs:
        frame = gpd.read_file(tri_member_uri(tri_archive, member_name), bbox=bbox)
        if frame.empty:
            continue
        metadata = tri_metadata_for_scenario_key(scenario_key)
        trimmed = frame[["geometry"]].copy()
        trimmed["tri_member_name"] = Path(member_name).name
        trimmed["tri_scenario_key"] = normalize_tri_scenario_key(scenario_key)
        trimmed["tri_scenario_code"] = metadata["canonical_code"]
        trimmed["tri_scenario_label"] = metadata["scenario_label"]
        trimmed["tri_level"] = metadata["tri_level"]
        frames.append(trimmed)

    if not frames:
        return gpd.GeoDataFrame(
            {
                "geometry": [],
                "tri_member_name": [],
                "tri_scenario_key": [],
                "tri_scenario_code": [],
                "tri_scenario_label": [],
                "tri_level": [],
            },
            geometry="geometry",
            crs=4326,
        )

    merged = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True),
        geometry="geometry",
        crs=frames[0].crs,
    )
    if merged.crs is None:
        merged = merged.set_crs(4326)
    elif str(merged.crs) != "EPSG:4326":
        merged = merged.to_crs(4326)
    return merged


def load_plain_polygon_members(
    tri_archive: Path,
    member_names: Iterable[str],
    *,
    bbox: tuple[float, float, float, float] | None,
) -> gpd.GeoDataFrame:
    frames: list[gpd.GeoDataFrame] = []
    for member_name in member_names:
        if not member_name:
            continue
        frame = gpd.read_file(tri_member_uri(tri_archive, member_name), bbox=bbox)
        if frame.empty:
            continue
        frames.append(frame[["geometry"]].copy())

    if not frames:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=4326)

    merged = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True),
        geometry="geometry",
        crs=frames[0].crs,
    )
    if merged.crs is None:
        merged = merged.set_crs(4326)
    elif str(merged.crs) != "EPSG:4326":
        merged = merged.to_crs(4326)
    return merged


def transform_bbox_from_4326(
    bbox: tuple[float, float, float, float],
    target_crs: Any,
) -> tuple[float, float, float, float]:
    bbox_series = gpd.GeoSeries([box(*bbox)], crs=4326).to_crs(target_crs)
    return tuple(bbox_series.total_bounds.tolist())


def list_riparian_shapefiles(riparian_root: Path) -> list[Path]:
    if not riparian_root.exists():
        return []
    return sorted(riparian_root.rglob("rpz_*.shp"))


def load_riparian_polygons(
    riparian_root: Path,
    *,
    bbox: tuple[float, float, float, float] | None,
) -> gpd.GeoDataFrame:
    if riparian_root is None or not riparian_root.exists():
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=4326)

    frames: list[gpd.GeoDataFrame] = []
    for shapefile_path in list_riparian_shapefiles(riparian_root):
        sample = gpd.read_file(shapefile_path, rows=1)
        sample_crs = sample.crs or "EPSG:4326"
        read_bbox = bbox
        if bbox is not None and str(sample_crs) != "EPSG:4326":
            read_bbox = transform_bbox_from_4326(bbox, sample_crs)

        frame = gpd.read_file(shapefile_path, bbox=read_bbox)
        if frame.empty:
            continue

        keep_columns = ["geometry"]
        if "DU_ID" in frame.columns:
            keep_columns.append("DU_ID")
        trimmed = frame[keep_columns].copy()
        trimmed["riparian_source_file"] = shapefile_path.name
        frames.append(trimmed)

    if not frames:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=4326)

    merged = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True),
        geometry="geometry",
        crs=frames[0].crs,
    )
    if merged.crs is None:
        merged = merged.set_crs(4326)
    elif str(merged.crs) != "EPSG:4326":
        merged = merged.to_crs(4326)
    return merged


def point_ids_intersecting_polygons(
    points_gdf: gpd.GeoDataFrame,
    point_id_col: str,
    polygon_gdf: gpd.GeoDataFrame,
) -> set[Any]:
    if points_gdf.empty or polygon_gdf.empty:
        return set()
    joined = gpd.sjoin(
        points_gdf[[point_id_col, "geometry"]],
        polygon_gdf[["geometry"]],
        how="inner",
        predicate="intersects",
    )
    return set(joined[point_id_col].dropna().tolist())


def classify_points_against_tri(
    points_gdf: gpd.GeoDataFrame,
    point_columns: PointColumns,
    tri_archive: Path,
    riparian_root: Path | None = None,
) -> pd.DataFrame:
    point_id_col = point_columns.point_id
    if points_gdf.empty:
        return pd.DataFrame(
            columns=[
                point_id_col,
                "tri_for_hit",
                "tri_boundary_hit",
                "tri_zone_status",
                "riparian_hit",
            ]
        )

    bbox = tuple(points_gdf.total_bounds.tolist())
    for_member_specs = list_tri_for_members(tri_archive)
    tri_for_polygons = load_tri_polygon_members(tri_archive, for_member_specs, bbox=bbox)
    tri_boundary_member = find_tri_member_by_filename(tri_archive, TRI_BOUNDARY_FILENAME)
    tri_boundary_polygons = load_plain_polygon_members(
        tri_archive,
        [tri_boundary_member] if tri_boundary_member else [],
        bbox=bbox,
    )
    riparian_polygons = (
        load_riparian_polygons(riparian_root, bbox=bbox)
        if riparian_root is not None
        else gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=4326)
    )

    base_points = points_gdf[[point_id_col, "geometry"]].drop_duplicates(subset=[point_id_col]).copy()
    classification_df = base_points[[point_id_col]].copy()

    tri_for_ids = point_ids_intersecting_polygons(base_points, point_id_col, tri_for_polygons)
    tri_boundary_ids = point_ids_intersecting_polygons(base_points, point_id_col, tri_boundary_polygons)
    riparian_candidate_points = base_points.loc[
        ~base_points[point_id_col].isin(tri_for_ids)
        & ~base_points[point_id_col].isin(tri_boundary_ids)
    ].copy()
    riparian_ids = point_ids_intersecting_polygons(
        riparian_candidate_points,
        point_id_col,
        riparian_polygons,
    )

    classification_df["tri_for_hit"] = classification_df[point_id_col].isin(tri_for_ids)
    classification_df["tri_boundary_hit"] = classification_df[point_id_col].isin(tri_boundary_ids)
    classification_df["riparian_hit"] = classification_df[point_id_col].isin(riparian_ids)
    classification_df["tri_zone_status"] = np.select(
        [
            classification_df["tri_for_hit"],
            ~classification_df["tri_for_hit"] & classification_df["tri_boundary_hit"],
        ],
        [
            "for",
            "inside_n_tri_not_for",
        ],
        default="outside_n_tri",
    )
    return classification_df


def resolve_raster_paths(candidate_df: pd.DataFrame, flood_dir: Path) -> pd.DataFrame:
    resolved_cache: dict[tuple[str, Any, Any], Path | None] = {}

    def _resolve(row: pd.Series) -> Path | None:
        key = (str(row["raster_file"]), row.get("source_year_folder"), str(row.get("raster_path")))
        if key in resolved_cache:
            return resolved_cache[key]

        raw_raster_path = row.get("raster_path")
        if pd.notna(raw_raster_path):
            path = Path(str(raw_raster_path))
            if path.exists():
                resolved_cache[key] = path.resolve()
                return resolved_cache[key]

        raster_file = str(row["raster_file"])
        source_year = row.get("source_year_folder")
        candidates: list[Path] = []
        if pd.notna(source_year):
            year_text = str(int(source_year))
            candidates.extend(
                [
                    flood_dir / year_text / raster_file,
                    flood_dir / f"{year_text}_filtered" / raster_file,
                ]
            )
        candidates.append(flood_dir / raster_file)

        for candidate in candidates:
            if candidate.exists():
                resolved_cache[key] = candidate.resolve()
                return resolved_cache[key]

        matches = list(flood_dir.rglob(raster_file))
        resolved_cache[key] = matches[0].resolve() if matches else None
        return resolved_cache[key]

    result = candidate_df.copy()
    result["resolved_raster_path"] = result.apply(_resolve, axis=1)
    result["raster_path_found"] = result["resolved_raster_path"].notna()
    return result


def empty_buffer_stats(prefix: str, total_pixels: int = 0) -> dict[str, Any]:
    return {
        f"{prefix}_flood_hit": False,
        f"{prefix}_total_pixels": total_pixels,
        f"{prefix}_flooded_pixels": 0,
        f"{prefix}_flooded_pixel_pct": 0.0,
        f"{prefix}_flooded_area_m2": 0.0,
        f"{prefix}_min_depth_cm": np.nan,
        f"{prefix}_max_depth_cm": np.nan,
        f"{prefix}_median_depth_cm": np.nan,
        f"{prefix}_mean_depth_cm": np.nan,
    }


def compute_buffer_stats(
    src: rasterio.io.DatasetReader,
    x: float,
    y: float,
    radius_m: float,
    threshold_cm: float,
    prefix: str,
) -> dict[str, Any]:
    geom = Point(x, y).buffer(radius_m)
    try:
        window = geometry_window(src, [mapping(geom)])
    except WindowError:
        return empty_buffer_stats(prefix)

    data = src.read(1, window=window, masked=True)
    arr = np.asarray(data)
    inside = geometry_mask(
        [mapping(geom)],
        out_shape=arr.shape,
        transform=src.window_transform(window),
        invert=True,
        all_touched=True,
    )

    total_pixels = int(inside.sum())
    if total_pixels == 0:
        return empty_buffer_stats(prefix)

    valid = inside.copy()
    if np.ma.isMaskedArray(data):
        valid &= ~np.asarray(data.mask)
    valid &= arr != PERMANENT_WATER_VALUE
    valid &= arr > threshold_cm

    if not valid.any():
        return empty_buffer_stats(prefix, total_pixels=total_pixels)

    values = arr[valid].astype(float)
    flooded_pixels = int(values.size)
    pixel_area_m2 = abs(src.res[0] * src.res[1])
    return {
        f"{prefix}_flood_hit": True,
        f"{prefix}_total_pixels": total_pixels,
        f"{prefix}_flooded_pixels": flooded_pixels,
        f"{prefix}_flooded_pixel_pct": float((flooded_pixels / total_pixels) * 100.0),
        f"{prefix}_flooded_area_m2": float(flooded_pixels * pixel_area_m2),
        f"{prefix}_min_depth_cm": float(values.min()),
        f"{prefix}_max_depth_cm": float(values.max()),
        f"{prefix}_median_depth_cm": float(np.median(values)),
        f"{prefix}_mean_depth_cm": float(values.mean()),
    }


def inspect_candidate_events(
    candidate_df: pd.DataFrame,
    point_columns: PointColumns,
    point_buffer_m: float,
    surrounding_buffer_km: float,
    threshold_cm: float,
) -> pd.DataFrame:
    valid_candidates = candidate_df[candidate_df["event_id"].notna() & candidate_df["raster_path_found"]].copy()
    if valid_candidates.empty:
        return pd.DataFrame(
            columns=[
                "point_id",
                "event_id",
                "hit_at_point",
                "point_buffer_total_pixels",
                "point_buffer_flood_hit",
                "point_buffer_flooded_pixels",
                "point_buffer_flooded_pixel_pct",
                "point_buffer_flooded_area_m2",
                "point_buffer_min_depth_cm",
                "point_buffer_max_depth_cm",
                "point_buffer_median_depth_cm",
                "point_buffer_mean_depth_cm",
                "point_buffer_radius_m",
                "buffer_total_pixels",
                "buffer_flood_hit",
                "buffer_flooded_pixels",
                "buffer_flooded_pixel_pct",
                "buffer_flooded_area_m2",
                "buffer_min_depth_cm",
                "buffer_max_depth_cm",
                "buffer_median_depth_cm",
                "buffer_mean_depth_cm",
                "buffer_radius_km",
                "surrounding_buffer_total_pixels",
                "surrounding_buffer_flood_hit",
                "surrounding_buffer_flooded_pixels",
                "surrounding_buffer_flooded_pixel_pct",
                "surrounding_buffer_flooded_area_m2",
                "surrounding_buffer_min_depth_cm",
                "surrounding_buffer_max_depth_cm",
                "surrounding_buffer_median_depth_cm",
                "surrounding_buffer_mean_depth_cm",
                "surrounding_buffer_radius_km",
                "exact_point_depth_cm",
            ]
        )

    results: list[dict[str, Any]] = []
    surrounding_radius_m = surrounding_buffer_km * 1000.0

    for raster_path_value, group in valid_candidates.groupby("resolved_raster_path", sort=False):
        raster_path = Path(str(raster_path_value))
        with rasterio.open(raster_path) as src:
            transformer = Transformer.from_crs(4326, src.crs, always_xy=True)
            for row in group.to_dict("records"):
                lon = float(row[point_columns.longitude])
                lat = float(row[point_columns.latitude])
                x, y = transformer.transform(lon, lat)

                point_buffer_stats = compute_buffer_stats(
                    src,
                    x,
                    y,
                    point_buffer_m,
                    threshold_cm,
                    prefix="point_buffer",
                )
                surrounding_buffer_stats = compute_buffer_stats(
                    src,
                    x,
                    y,
                    surrounding_radius_m,
                    threshold_cm,
                    prefix="surrounding_buffer",
                )
                results.append(
                    {
                        "point_id": row[point_columns.point_id],
                        "event_id": row["event_id"],
                        "hit_at_point": point_buffer_stats["point_buffer_flood_hit"],
                        "exact_point_depth_cm": point_buffer_stats["point_buffer_max_depth_cm"],
                        "point_buffer_radius_m": point_buffer_m,
                        "buffer_total_pixels": surrounding_buffer_stats["surrounding_buffer_total_pixels"],
                        "buffer_flood_hit": surrounding_buffer_stats["surrounding_buffer_flood_hit"],
                        "buffer_flooded_pixels": surrounding_buffer_stats["surrounding_buffer_flooded_pixels"],
                        "buffer_flooded_pixel_pct": surrounding_buffer_stats["surrounding_buffer_flooded_pixel_pct"],
                        "buffer_flooded_area_m2": surrounding_buffer_stats["surrounding_buffer_flooded_area_m2"],
                        "buffer_min_depth_cm": surrounding_buffer_stats["surrounding_buffer_min_depth_cm"],
                        "buffer_max_depth_cm": surrounding_buffer_stats["surrounding_buffer_max_depth_cm"],
                        "buffer_median_depth_cm": surrounding_buffer_stats["surrounding_buffer_median_depth_cm"],
                        "buffer_mean_depth_cm": surrounding_buffer_stats["surrounding_buffer_mean_depth_cm"],
                        "buffer_radius_km": surrounding_buffer_km,
                        "surrounding_buffer_radius_km": surrounding_buffer_km,
                        **point_buffer_stats,
                        **surrounding_buffer_stats,
                    }
                )

    inspected_df = pd.DataFrame(results)
    return inspected_df


def build_combined_flood_flag_columns(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()

    for column, default_value in {
        "gaspar_commune_hit": False,
        "tri_for_hit": False,
        "tri_boundary_hit": False,
        "riparian_hit": False,
    }.items():
        if column not in result.columns:
            result[column] = default_value
        result[column] = result[column].fillna(default_value).astype(bool)

    if "tri_zone_status" not in result.columns:
        result["tri_zone_status"] = pd.Series("outside_n_tri", index=result.index, dtype="string")
    else:
        result["tri_zone_status"] = (
            result["tri_zone_status"].astype("string").fillna("outside_n_tri").str.lower()
        )

    case_a_mask = result["jrc_flood_hit"].fillna(False)
    gaspar_branch_mask = ~case_a_mask & result["gaspar_commune_hit"]
    case_b_mask = gaspar_branch_mask & result["tri_for_hit"]
    case_c_mask = (
        gaspar_branch_mask
        & ~result["tri_for_hit"]
        & ~result["tri_boundary_hit"]
        & result["riparian_hit"]
    )

    result["flag_jrc"] = np.where(case_a_mask, 1, 0).astype(int)
    result["flag_gaspar"] = np.where(gaspar_branch_mask, 1, 0).astype(int)

    result["flag_flood"] = np.where(case_a_mask | case_b_mask | case_c_mask, 1, 0).astype(int)
    result["flag_flood_source"] = np.select(
        [
            case_a_mask,
            case_b_mask,
            case_c_mask,
        ],
        [
            "jrc",
            "gaspar",
            "gaspar",
        ],
        default="none",
    )
    result["flag_flood_case"] = np.select(
        [
            case_a_mask,
            case_b_mask,
            case_c_mask,
        ],
        [
            "case_a_jrc",
            "case_b_gaspar_tri_for",
            "case_c_gaspar_riparian",
        ],
        default="none",
    )

    result["flag_flood_start_date"] = pd.NaT
    result["flag_flood_end_date"] = pd.NaT
    result.loc[case_a_mask, "flag_flood_start_date"] = result.loc[case_a_mask, "first_hit_start_date"]
    result.loc[case_a_mask, "flag_flood_end_date"] = result.loc[case_a_mask, "last_hit_end_date"]
    gaspar_flag_mask = case_b_mask | case_c_mask
    result.loc[gaspar_flag_mask, "flag_flood_start_date"] = result.loc[
        gaspar_flag_mask,
        "gaspar_first_start_date",
    ]
    result.loc[gaspar_flag_mask, "flag_flood_end_date"] = result.loc[
        gaspar_flag_mask,
        "gaspar_last_end_date",
    ]
    result["flag_flood_date_source"] = np.where(case_a_mask, "jrc", np.where(gaspar_flag_mask, "gaspar", "none"))

    result["flag_flood_decision_path"] = np.select(
        [
            case_a_mask,
            ~case_a_mask & ~result["gaspar_commune_hit"],
            case_b_mask,
            gaspar_branch_mask & ~result["tri_for_hit"] & result["tri_boundary_hit"],
            case_c_mask,
            gaspar_branch_mask & ~result["tri_for_hit"] & ~result["tri_boundary_hit"] & ~result["riparian_hit"],
        ],
        [
            "jrc_positive_local_flood_hit",
            "no_jrc_hit_and_no_gaspar_commune_event",
            "no_jrc_hit_gaspar_tri_for",
            "no_jrc_hit_gaspar_inside_n_tri_not_for",
            "no_jrc_hit_gaspar_riparian",
            "no_jrc_hit_gaspar_outside_n_tri_and_riparian",
        ],
        default="no_positive_flag_case",
    )
    result["flag_flood_notes"] = np.select(
        [
            case_a_mask,
            ~case_a_mask & ~result["gaspar_commune_hit"],
            case_b_mask,
            gaspar_branch_mask & ~result["tri_for_hit"] & result["tri_boundary_hit"],
            case_c_mask,
            gaspar_branch_mask & ~result["tri_for_hit"] & ~result["tri_boundary_hit"] & ~result["riparian_hit"],
        ],
        [
            "Final flood flag is positive from the raster-confirmed JRC local hit.",
            "JRC stayed negative and no overlapping Gaspar commune event was found inside the study window.",
            "JRC stayed negative, but Gaspar found an overlapping commune event and the point lies inside a TRI For polygon.",
            "JRC stayed negative and Gaspar found an overlapping commune event, but the point is inside an n_tri boundary without matching a TRI For polygon.",
            "JRC stayed negative, Gaspar found an overlapping commune event, the point is outside n_tri, and it intersects a riparian polygon.",
            "JRC stayed negative, Gaspar found an overlapping commune event, and the point is outside both TRI For polygons and the riparian polygons.",
        ],
        default="No positive combined flood flag case was triggered.",
    )
    return result


def build_summary_table(
    original_points: pd.DataFrame,
    point_columns: PointColumns,
    points_with_lau: pd.DataFrame,
    candidate_df: pd.DataFrame,
    inspected_df: pd.DataFrame,
    default_date_inspected_df: pd.DataFrame | None,
    point_buffer_m: float,
    surrounding_buffer_km: float,
    threshold_cm: float,
    study_start: str | None,
    study_end: str | None,
    gaspar_candidate_df: pd.DataFrame | None = None,
    tri_classification_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    summary = original_points.copy()
    point_id_col = point_columns.point_id
    inspected_df = inspected_df.copy()
    gaspar_candidate_df = gaspar_candidate_df.copy() if gaspar_candidate_df is not None else pd.DataFrame()
    tri_classification_df = (
        tri_classification_df.copy() if tri_classification_df is not None else pd.DataFrame()
    )
    default_date_inspected_df = (
        default_date_inspected_df.copy() if default_date_inspected_df is not None else pd.DataFrame()
    )

    expected_inspected_columns: dict[str, Any] = {
        "point_buffer_total_pixels": 0,
        "point_buffer_flood_hit": False,
        "point_buffer_flooded_pixels": 0,
        "point_buffer_flooded_pixel_pct": 0.0,
        "point_buffer_flooded_area_m2": 0.0,
        "point_buffer_min_depth_cm": np.nan,
        "point_buffer_max_depth_cm": np.nan,
        "point_buffer_median_depth_cm": np.nan,
        "point_buffer_mean_depth_cm": np.nan,
        "surrounding_buffer_total_pixels": 0,
        "surrounding_buffer_flood_hit": False,
        "surrounding_buffer_flooded_pixels": 0,
        "surrounding_buffer_flooded_pixel_pct": 0.0,
        "surrounding_buffer_flooded_area_m2": 0.0,
        "surrounding_buffer_min_depth_cm": np.nan,
        "surrounding_buffer_max_depth_cm": np.nan,
        "surrounding_buffer_median_depth_cm": np.nan,
        "surrounding_buffer_mean_depth_cm": np.nan,
    }
    for column, default_value in expected_inspected_columns.items():
        if column not in inspected_df.columns:
            inspected_df[column] = default_value
        if column not in default_date_inspected_df.columns:
            default_date_inspected_df[column] = default_value

    point_metadata_cols = [
        point_id_col,
        "excel_row_number",
        "lau_code",
        "lau_code_local",
        "lau_name",
        "country_code",
        "population_2024",
        "area_km2",
        "insee_com",
        "commune_name_adminexpress",
        "insee_dep",
        "insee_reg",
        "nuts3_code",
        "nuts3_name",
    ]
    point_metadata_cols = [col for col in point_metadata_cols if col in points_with_lau.columns]
    summary = summary.merge(
        points_with_lau[point_metadata_cols].drop_duplicates(subset=[point_id_col]),
        on=point_id_col,
        how="left",
    )

    candidate_only = candidate_df[candidate_df["event_id"].notna()].copy()
    candidate_agg = (
        candidate_only.groupby(point_id_col)
        .agg(
            candidate_event_count=("event_id", "nunique"),
            candidate_first_start_date=("start_date", "min"),
            candidate_last_end_date=("end_date", "max"),
            candidate_raster_found_count=("raster_path_found", "sum"),
        )
        .reset_index()
    )

    inspected_agg = pd.DataFrame(columns=[point_id_col])
    if not inspected_df.empty:
        hits_only = inspected_df[
            inspected_df["surrounding_buffer_flood_hit"] | inspected_df["point_buffer_flood_hit"]
        ].copy()
        inspected_agg = (
            inspected_df.groupby("point_id")
            .agg(
                checked_event_count=("event_id", "nunique"),
                hit_at_point_event_count=("point_buffer_flood_hit", "sum"),
                hit_within_buffer_event_count=("surrounding_buffer_flood_hit", "sum"),
                max_exact_point_depth_cm=("point_buffer_max_depth_cm", "max"),
                max_point_buffer_depth_cm=("point_buffer_max_depth_cm", "max"),
                max_point_buffer_median_depth_cm=("point_buffer_median_depth_cm", "max"),
                max_point_buffer_mean_depth_cm=("point_buffer_mean_depth_cm", "max"),
                max_point_buffer_flooded_pixels=("point_buffer_flooded_pixels", "max"),
                max_point_buffer_flooded_area_m2=("point_buffer_flooded_area_m2", "max"),
                max_buffer_depth_cm=("buffer_max_depth_cm", "max"),
                max_buffer_median_depth_cm=("buffer_median_depth_cm", "max"),
                max_buffer_mean_depth_cm=("buffer_mean_depth_cm", "max"),
                max_buffer_flooded_pixels=("buffer_flooded_pixels", "max"),
                max_buffer_flooded_area_m2=("buffer_flooded_area_m2", "max"),
            )
            .reset_index()
            .rename(columns={"point_id": point_id_col})
        )
        if not hits_only.empty:
            candidate_event_dates = candidate_only[[point_id_col, "event_id", "start_date", "end_date"]].drop_duplicates()
            candidate_event_dates = candidate_event_dates.rename(columns={point_id_col: "point_id"})
            hit_dates = (
                hits_only.merge(
                    candidate_event_dates,
                    on=["point_id", "event_id"],
                    how="left",
                )
                .groupby("point_id")
                .agg(
                    first_hit_start_date=("start_date", "min"),
                    last_hit_end_date=("end_date", "max"),
                    hit_event_count=("event_id", "nunique"),
                )
                .reset_index()
                .rename(columns={"point_id": point_id_col})
            )
            inspected_agg = inspected_agg.merge(hit_dates, on=point_id_col, how="left")

    if not default_date_inspected_df.empty:
        default_date_hits_only = default_date_inspected_df[
            default_date_inspected_df["surrounding_buffer_flood_hit"] | default_date_inspected_df["point_buffer_flood_hit"]
        ].copy()
        if not default_date_hits_only.empty:
            default_date_hit_counts = (
                default_date_hits_only.groupby("point_id")
                .agg(hit_event_count_until_default_date=("event_id", "nunique"))
                .reset_index()
                .rename(columns={"point_id": point_id_col})
            )
            inspected_agg = inspected_agg.merge(default_date_hit_counts, on=point_id_col, how="left")

    summary = summary.merge(candidate_agg, on=point_id_col, how="left")
    summary = summary.merge(inspected_agg, on=point_id_col, how="left")

    if not gaspar_candidate_df.empty and "gaspar_event_uid" in gaspar_candidate_df.columns:
        gaspar_only = gaspar_candidate_df[gaspar_candidate_df["gaspar_event_uid"].notna()].copy()
        if not gaspar_only.empty:
            gaspar_agg = (
                gaspar_only.groupby(point_id_col)
                .agg(
                    gaspar_candidate_event_count=("gaspar_event_uid", "nunique"),
                    gaspar_candidate_decree_count=("cod_nat_catnat", "nunique"),
                    gaspar_first_start_date=("gaspar_start_date", "min"),
                    gaspar_last_end_date=("gaspar_end_date", "max"),
                )
                .reset_index()
            )
            summary = summary.merge(gaspar_agg, on=point_id_col, how="left")

    if not tri_classification_df.empty:
        tri_cols = [
            point_id_col,
            "tri_for_hit",
            "tri_boundary_hit",
            "tri_zone_status",
            "riparian_hit",
        ]
        tri_cols = [column for column in tri_cols if column in tri_classification_df.columns]
        if tri_cols:
            summary = summary.merge(
                tri_classification_df[tri_cols].drop_duplicates(subset=[point_id_col]),
                on=point_id_col,
                how="left",
            )

    expected_summary_columns: dict[str, Any] = {
        "checked_event_count": np.nan,
        "hit_at_point_event_count": np.nan,
        "hit_within_buffer_event_count": np.nan,
        "hit_event_count_until_default_date": np.nan,
        "max_exact_point_depth_cm": np.nan,
        "max_point_buffer_depth_cm": np.nan,
        "max_point_buffer_median_depth_cm": np.nan,
        "max_point_buffer_mean_depth_cm": np.nan,
        "max_point_buffer_flooded_pixels": np.nan,
        "max_point_buffer_flooded_area_m2": np.nan,
        "max_buffer_depth_cm": np.nan,
        "max_buffer_median_depth_cm": np.nan,
        "max_buffer_mean_depth_cm": np.nan,
        "max_buffer_flooded_pixels": np.nan,
        "max_buffer_flooded_area_m2": np.nan,
        "first_hit_start_date": pd.NaT,
        "last_hit_end_date": pd.NaT,
        "hit_event_count": np.nan,
        "gaspar_candidate_event_count": np.nan,
        "gaspar_candidate_decree_count": np.nan,
        "gaspar_first_start_date": pd.NaT,
        "gaspar_last_end_date": pd.NaT,
    }
    for column, default_value in expected_summary_columns.items():
        if column not in summary.columns:
            summary[column] = default_value
    if "study_period_anchor_date" in summary.columns:
        anchor_mask = summary["study_period_anchor_date"].notna()
        summary.loc[anchor_mask, "hit_event_count_until_default_date"] = (
            summary.loc[anchor_mask, "hit_event_count_until_default_date"].fillna(0)
        )

    summary["point_buffer_radius_m"] = point_buffer_m
    summary["buffer_radius_km"] = surrounding_buffer_km
    summary["surrounding_buffer_radius_km"] = surrounding_buffer_km
    summary["flood_threshold_cm"] = threshold_cm
    if "study_period_start" not in summary.columns:
        summary["study_period_start"] = study_start if study_start else pd.NA
    if "study_period_end" not in summary.columns:
        summary["study_period_end"] = study_end if study_end else pd.NA
    summary["lau_matched"] = summary["lau_code"].notna()
    summary["lau_touched_by_any_jrc_event"] = summary["candidate_event_count"].fillna(0).gt(0)
    summary["jrc_flood_hit"] = summary["hit_event_count"].fillna(0).gt(0)
    summary["jrc_flood_flag"] = np.where(summary["jrc_flood_hit"], "yes", "no")
    summary["gaspar_commune_hit"] = summary["gaspar_candidate_event_count"].fillna(0).gt(0)

    summary["decision_path"] = np.select(
        [
            ~summary["lau_matched"],
            summary["lau_matched"] & ~summary["lau_touched_by_any_jrc_event"],
            summary["lau_touched_by_any_jrc_event"] & ~summary["jrc_flood_hit"],
            summary["jrc_flood_hit"],
        ],
        [
            "point_outside_lau",
            "lau_not_touched_in_processed_jrc_events",
            "candidate_events_checked_but_no_local_flood_pixel",
            "positive_local_flood_hit",
        ],
        default="unknown",
    )

    summary["notes"] = np.select(
        [
            ~summary["lau_matched"],
            summary["lau_matched"] & ~summary["lau_touched_by_any_jrc_event"],
            summary["lau_touched_by_any_jrc_event"] & ~summary["jrc_flood_hit"],
            summary["jrc_flood_hit"],
        ],
        [
            "Point did not fall inside any LAU polygon in the supplied LAU dataset.",
            "The mapped LAU never appears in the processed JRC LAU event table, so no raster checks were needed.",
            "The LAU was touched by one or more JRC events, but no flooded pixel above threshold was found inside the 40 m point buffer or the 1 km surrounding buffer.",
            "At least one JRC event produced flooded pixels above threshold inside the 40 m point buffer or the 1 km surrounding buffer.",
        ],
        default="",
    )

    return build_combined_flood_flag_columns(summary)


def build_candidate_sheet(
    candidate_df: pd.DataFrame,
    point_columns: PointColumns,
    inspected_df: pd.DataFrame,
    row_study_period_columns: RowStudyPeriodColumns | None = None,
) -> pd.DataFrame:
    candidate_only = candidate_df[candidate_df["event_id"].notna()].copy()
    if candidate_only.empty:
        return candidate_only

    candidate_only = candidate_only.rename(
        columns={
            point_columns.point_id: "point_id",
            point_columns.latitude: "point_latitude",
            point_columns.longitude: "point_longitude",
        }
    )
    if point_columns.city and point_columns.city in candidate_only.columns:
        candidate_only = candidate_only.rename(columns={point_columns.city: "point_city"})

    if not inspected_df.empty:
        candidate_only = candidate_only.merge(
            inspected_df,
            on=["point_id", "event_id"],
            how="left",
        )

    expected_inspection_columns: dict[str, Any] = {
        "hit_at_point": False,
        "exact_point_depth_cm": np.nan,
        "point_buffer_total_pixels": 0,
        "point_buffer_flood_hit": False,
        "point_buffer_flooded_pixels": 0,
        "point_buffer_flooded_pixel_pct": 0.0,
        "point_buffer_flooded_area_m2": 0.0,
        "point_buffer_min_depth_cm": np.nan,
        "point_buffer_max_depth_cm": np.nan,
        "point_buffer_median_depth_cm": np.nan,
        "point_buffer_mean_depth_cm": np.nan,
        "point_buffer_radius_m": np.nan,
        "buffer_total_pixels": 0,
        "buffer_flood_hit": False,
        "buffer_flooded_pixels": 0,
        "buffer_flooded_pixel_pct": 0.0,
        "buffer_flooded_area_m2": 0.0,
        "buffer_min_depth_cm": np.nan,
        "buffer_max_depth_cm": np.nan,
        "buffer_median_depth_cm": np.nan,
        "buffer_mean_depth_cm": np.nan,
        "buffer_radius_km": np.nan,
        "surrounding_buffer_total_pixels": 0,
        "surrounding_buffer_flood_hit": False,
        "surrounding_buffer_flooded_pixels": 0,
        "surrounding_buffer_flooded_pixel_pct": 0.0,
        "surrounding_buffer_flooded_area_m2": 0.0,
        "surrounding_buffer_min_depth_cm": np.nan,
        "surrounding_buffer_max_depth_cm": np.nan,
        "surrounding_buffer_median_depth_cm": np.nan,
        "surrounding_buffer_mean_depth_cm": np.nan,
        "surrounding_buffer_radius_km": np.nan,
    }
    for column, default_value in expected_inspection_columns.items():
        if column not in candidate_only.columns:
            candidate_only[column] = default_value

    period_cols: list[str] = []
    if row_study_period_columns:
        for raw_col in [
            row_study_period_columns.anchor,
            row_study_period_columns.primary_end,
            row_study_period_columns.fallback_end,
        ]:
            if raw_col and raw_col in candidate_only.columns and raw_col not in period_cols:
                period_cols.append(raw_col)
    for derived_col in ROW_STUDY_PERIOD_OUTPUT_COLUMNS:
        if derived_col in candidate_only.columns and derived_col not in period_cols:
            period_cols.append(derived_col)

    ordered_cols = [
        "point_id",
        "point_city",
        "excel_row_number",
        "point_latitude",
        "point_longitude",
        "lau_code",
        "lau_name",
        "insee_com",
        "insee_dep",
        "nuts3_code",
        "nuts3_name",
        *period_cols,
        "event_id",
        "raster_file",
        "resolved_raster_path",
        "start_date",
        "end_date",
        "duration_days",
        "max_depth_cm",
        "flooded_pixels",
        "flooded_area_m2",
        "raster_path_found",
        "hit_at_point",
        "exact_point_depth_cm",
        "point_buffer_total_pixels",
        "point_buffer_flood_hit",
        "point_buffer_flooded_pixels",
        "point_buffer_flooded_pixel_pct",
        "point_buffer_flooded_area_m2",
        "point_buffer_min_depth_cm",
        "point_buffer_max_depth_cm",
        "point_buffer_median_depth_cm",
        "point_buffer_mean_depth_cm",
        "point_buffer_radius_m",
        "buffer_total_pixels",
        "buffer_flood_hit",
        "buffer_flooded_pixels",
        "buffer_flooded_pixel_pct",
        "buffer_flooded_area_m2",
        "buffer_min_depth_cm",
        "buffer_max_depth_cm",
        "buffer_median_depth_cm",
        "buffer_mean_depth_cm",
        "buffer_radius_km",
        "surrounding_buffer_total_pixels",
        "surrounding_buffer_flood_hit",
        "surrounding_buffer_flooded_pixels",
        "surrounding_buffer_flooded_pixel_pct",
        "surrounding_buffer_flooded_area_m2",
        "surrounding_buffer_min_depth_cm",
        "surrounding_buffer_max_depth_cm",
        "surrounding_buffer_median_depth_cm",
        "surrounding_buffer_mean_depth_cm",
        "surrounding_buffer_radius_km",
    ]
    available = [column for column in ordered_cols if column in candidate_only.columns]
    return candidate_only[available].sort_values(["point_id", "start_date", "event_id"]).copy()


def build_hits_sheet(candidate_sheet: pd.DataFrame) -> pd.DataFrame:
    if candidate_sheet.empty:
        return candidate_sheet
    if "surrounding_buffer_flood_hit" not in candidate_sheet.columns:
        candidate_sheet = candidate_sheet.copy()
        candidate_sheet["surrounding_buffer_flood_hit"] = candidate_sheet.get("buffer_flood_hit", False)
    if "point_buffer_flood_hit" not in candidate_sheet.columns:
        candidate_sheet = candidate_sheet.copy()
        candidate_sheet["point_buffer_flood_hit"] = candidate_sheet.get("hit_at_point", False)
    hits = candidate_sheet[
        candidate_sheet["surrounding_buffer_flood_hit"].fillna(False)
        | candidate_sheet["point_buffer_flood_hit"].fillna(False)
    ].copy()
    available = [column for column in JRC_EVENT_HITS_COLUMNS if column in hits.columns]
    return hits[available].copy()


def build_jrc_output_summary_sheet(summary_df: pd.DataFrame) -> pd.DataFrame:
    drop_columns = [
        "gaspar_commune_hit",
        "gaspar_candidate_event_count",
        "gaspar_candidate_decree_count",
        "gaspar_first_start_date",
        "gaspar_last_end_date",
        "tri_for_hit",
        "tri_boundary_hit",
        "tri_zone_status",
        "riparian_hit",
        "tri_flood_risk_high_hit",
        "tri_flood_risk_medium_hit",
        "tri_flood_risk_low_hit",
        "tri_flood_risk_other_hit",
        "flood_risk_area_value",
        "TRI",
        "tri_scenario_codes",
        "tri_scenario_labels",
        "riparian_zone_hit",
        "flag_jrc",
        "flag_gaspar",
        "flag_flood",
        "flag_flood_source",
        "flag_flood_case",
        "flag_flood_start_date",
        "flag_flood_end_date",
        "flag_flood_date_source",
        "flag_flood_decision_path",
        "flag_flood_notes",
    ]
    keep_columns = [column for column in summary_df.columns if column not in drop_columns]
    return summary_df[keep_columns].copy()


def build_point_flag_sheet(
    points_df: pd.DataFrame,
    point_id_col: str,
    hit_point_ids: set[Any],
    *,
    flag_column: str = "flag_flood",
) -> pd.DataFrame:
    result = (
        points_df[[point_id_col]]
        .drop_duplicates(subset=[point_id_col])
        .rename(columns={point_id_col: "point_id"})
        .copy()
    )
    result[flag_column] = result["point_id"].isin(hit_point_ids).astype(int)
    return result.sort_values("point_id").reset_index(drop=True)


def build_detailed_sheet(
    points_df: pd.DataFrame,
    point_id_col: str,
    hit_point_ids: set[Any],
    *,
    touch_column: str = "touched",
) -> pd.DataFrame:
    result = points_df.copy()
    if point_id_col != "point_id":
        result.insert(0, "point_id", result[point_id_col])
    result.insert(
        1 if "point_id" in result.columns and result.columns[0] == "point_id" else 0,
        touch_column,
        result[point_id_col].isin(hit_point_ids).astype(int),
    )
    leading_cols = ["point_id", touch_column]
    ordered_cols = leading_cols + [column for column in result.columns if column not in leading_cols]
    return result[ordered_cols].copy()


def build_gaspar_candidate_sheet(
    gaspar_candidate_df: pd.DataFrame,
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
        "insee_com",
        "gaspar_event_uid",
        "cod_nat_catnat",
        "gaspar_start_date",
        "gaspar_end_date",
        "gaspar_commune_name",
        "gaspar_source_cod_commune",
        "gaspar_source_insee_com",
        "gaspar_commune_match_method",
        "tri_for_hit",
        "tri_boundary_hit",
        "tri_zone_status",
        "riparian_hit",
        "gaspar_spatial_hit",
        "gaspar_hit_reason",
    ]
    if gaspar_candidate_df.empty or "gaspar_event_uid" not in gaspar_candidate_df.columns:
        return pd.DataFrame(columns=expected_columns)

    point_id_col = point_columns.point_id
    gaspar_only = gaspar_candidate_df[gaspar_candidate_df["gaspar_event_uid"].notna()].copy()
    if gaspar_only.empty:
        return pd.DataFrame(columns=expected_columns)

    gaspar_only = gaspar_only.rename(
        columns={
            point_id_col: "point_id",
            point_columns.latitude: "point_latitude",
            point_columns.longitude: "point_longitude",
        }
    )
    if point_columns.city and point_columns.city in gaspar_only.columns:
        gaspar_only = gaspar_only.rename(columns={point_columns.city: "point_city"})

    tri_merge_cols = [
        point_id_col,
        "tri_for_hit",
        "tri_boundary_hit",
        "tri_zone_status",
        "riparian_hit",
    ]
    tri_merge_cols = [column for column in tri_merge_cols if column in tri_classification_df.columns]
    if tri_merge_cols:
        gaspar_only = gaspar_only.merge(
            tri_classification_df[tri_merge_cols].drop_duplicates(subset=[point_id_col]).rename(
                columns={point_id_col: "point_id"}
            ),
            on="point_id",
            how="left",
        )

    for column, default_value in {
        "tri_for_hit": False,
        "tri_boundary_hit": False,
        "riparian_hit": False,
    }.items():
        if column not in gaspar_only.columns:
            gaspar_only[column] = default_value
        gaspar_only[column] = gaspar_only[column].fillna(default_value).astype(bool)

    if "tri_zone_status" not in gaspar_only.columns:
        gaspar_only["tri_zone_status"] = "outside_n_tri"
    gaspar_only["tri_zone_status"] = (
        gaspar_only["tri_zone_status"].astype("string").fillna("outside_n_tri").str.lower()
    )

    riparian_mask = ~gaspar_only["tri_for_hit"] & ~gaspar_only["tri_boundary_hit"] & gaspar_only["riparian_hit"]
    gaspar_only["gaspar_spatial_hit"] = (gaspar_only["tri_for_hit"] | riparian_mask).astype(bool)
    gaspar_only["gaspar_hit_reason"] = np.select(
        [
            gaspar_only["tri_for_hit"],
            riparian_mask,
        ],
        [
            "tri_for",
            "riparian_outside_n_tri",
        ],
        default="not_selected",
    )

    preferred_order = [
        "point_id",
        "point_latitude",
        "point_longitude",
        "excel_row_number",
        "point_city",
        "lau_code",
        "lau_name",
        "insee_com",
        "gaspar_event_uid",
        "cod_nat_catnat",
        "gaspar_start_date",
        "gaspar_end_date",
        "gaspar_commune_name",
        "gaspar_source_cod_commune",
        "gaspar_source_insee_com",
        "gaspar_commune_match_method",
        "tri_for_hit",
        "tri_boundary_hit",
        "tri_zone_status",
        "riparian_hit",
        "gaspar_spatial_hit",
        "gaspar_hit_reason",
    ]
    if row_study_period_columns:
        for raw_col in [
            row_study_period_columns.anchor,
            row_study_period_columns.primary_end,
            row_study_period_columns.fallback_end,
        ]:
            if raw_col and raw_col in gaspar_only.columns and raw_col not in preferred_order:
                preferred_order.append(raw_col)
        for column in ROW_STUDY_PERIOD_OUTPUT_COLUMNS:
            if column in gaspar_only.columns and column not in preferred_order:
                preferred_order.append(column)
    available = [column for column in preferred_order if column in gaspar_only.columns]
    sort_columns = [column for column in ["point_id", "gaspar_start_date", "gaspar_event_uid"] if column in gaspar_only.columns]
    result = gaspar_only[available].copy()
    if sort_columns:
        result = result.sort_values(sort_columns)
    return result


def build_gaspar_hits_sheet(gaspar_candidate_sheet: pd.DataFrame) -> pd.DataFrame:
    if gaspar_candidate_sheet.empty or "gaspar_spatial_hit" not in gaspar_candidate_sheet.columns:
        return gaspar_candidate_sheet.copy()
    hits = gaspar_candidate_sheet[gaspar_candidate_sheet["gaspar_spatial_hit"].fillna(False)].copy()
    available = [column for column in GASPAR_EVENT_HITS_COLUMNS if column in hits.columns]
    return hits[available].copy()


def build_tri_reference_sheet() -> pd.DataFrame:
    rows = []
    for scenario_key, metadata in TRI_SCENARIO_METADATA.items():
        rows.append(
            {
                "tri_scenario_key": scenario_key,
                "tri_scenario_code": metadata["canonical_code"],
                "tri_level": metadata["tri_level"],
                "scenario_label": metadata["scenario_label"],
                "source_document": metadata["source_document"],
            }
        )
    return pd.DataFrame(rows).sort_values(["tri_level", "tri_scenario_code"]).reset_index(drop=True)


def write_output_workbook(
    output_path: Path,
    point_flag_sheet: pd.DataFrame,
    detailed_sheet: pd.DataFrame,
    candidate_sheet: pd.DataFrame,
    hits_sheet: pd.DataFrame,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        point_flag_sheet.to_excel(writer, sheet_name="point_flags", index=False)
        detailed_sheet.to_excel(writer, sheet_name="Detailed", index=False)
        candidate_sheet.to_excel(writer, sheet_name="candidate_events", index=False)
        hits_sheet.to_excel(writer, sheet_name="event_hits", index=False)


def write_gaspar_output_workbook(
    output_path: Path,
    point_flag_sheet: pd.DataFrame,
    detailed_sheet: pd.DataFrame,
    candidate_sheet: pd.DataFrame,
    hits_sheet: pd.DataFrame,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        point_flag_sheet.to_excel(writer, sheet_name="point_flags", index=False)
        detailed_sheet.to_excel(writer, sheet_name="Detailed", index=False)
        candidate_sheet.to_excel(writer, sheet_name="candidate_events", index=False)
        hits_sheet.to_excel(writer, sheet_name="event_hits", index=False)


def derive_gaspar_output_path(output_path: Path) -> Path:
    stem = output_path.stem
    if "jrc_flood_check" in stem:
        combined_stem = stem.replace("jrc_flood_check", "gaspar_check")
    else:
        combined_stem = f"{stem}_gaspar_check"
    if combined_stem == stem:
        combined_stem = f"{stem}_gaspar_check"
    return output_path.with_name(f"{combined_stem}{output_path.suffix}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check point coordinates against processed JRC flood events using a fast two-stage workflow: "
            "LAU prefilter first, then exact raster inspection only for candidate events."
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
    parser.add_argument("--events-file", default=str(DEFAULT_EVENT_TABLE), help="Processed LAU event table (.parquet or .csv).")
    parser.add_argument("--flood-dir", default=str(DEFAULT_FLOOD_DIR), help="Root directory containing the official JRC flood TIFF folders.")
    parser.add_argument("--france-lookup-file", default=str(DEFAULT_FRANCE_LOOKUP), help="Optional France LAU to INSEE lookup CSV for extra output columns.")
    parser.add_argument("--gaspar-file", default=str(DEFAULT_GASPAR_FILE), help="Optional processed Gaspar workbook used for the fallback flood flag branch.")
    parser.add_argument("--gaspar-sheet-name", default=DEFAULT_GASPAR_SHEET, help=f"Sheet name to read from the Gaspar workbook. Default: {DEFAULT_GASPAR_SHEET}.")
    parser.add_argument("--france-old-insee-updates-file", default=str(DEFAULT_FRANCE_OLD_INSEE_UPDATES), help="Historical old-INSEE to current-INSEE CSV used to resolve Gaspar communes.")
    parser.add_argument("--tri-archive", default=str(DEFAULT_TRI_ARCHIVE), help="National TRI source used for the simplified Gaspar fallback branch. Only the plain TRI For polygons and the n_tri territory boundaries are used. Accepts either the unpacked folder or the original zip archive.")
    parser.add_argument("--riparian-root", default=str(DEFAULT_RIPARIAN_ROOT), help="Root folder containing the unzipped France riparian shapefiles used only when a Gaspar point is outside both TRI For polygons and n_tri boundaries.")
    parser.add_argument("--disable-gaspar-fallback", action="store_true", help="Disable the Gaspar plus TRI plus riparian fallback branch and keep the final flood flag JRC-only.")
    parser.add_argument("--study-start", default=None, help="Optional study-period start date (YYYY-MM-DD). Keeps only events whose intervals overlap this bound.")
    parser.add_argument("--study-end", default=None, help="Optional study-period end date (YYYY-MM-DD). Keeps only events whose intervals overlap this bound.")
    parser.add_argument("--row-study-anchor-col", default=None, help="Optional workbook column used as the per-row anchor date when a lookback window is requested.")
    parser.add_argument("--row-study-end-col", default=None, help="Optional workbook column used as the preferred per-row study-period end date.")
    parser.add_argument("--row-study-end-fallback-col", default=None, help="Optional fallback workbook column used when the preferred per-row end date is empty.")
    parser.add_argument("--row-study-lookback-years", type=int, default=None, help="Optional years to subtract from the per-row anchor date. Leave blank to keep the full flood history up to the row end date.")
    parser.add_argument("--point-buffer-m", type=float, default=DEFAULT_POINT_BUFFER_M, help=f"Radius in meters used for the local point match metrics. Default: {DEFAULT_POINT_BUFFER_M:.0f}.")
    parser.add_argument("--buffer-km", type=float, default=DEFAULT_SURROUNDING_BUFFER_KM, help=f"Radius in kilometers used for the surrounding buffer metrics. Default: {DEFAULT_SURROUNDING_BUFFER_KM:.1f}.")
    parser.add_argument("--threshold-cm", type=float, default=0.0, help="Minimum depth in cm to count as flooded. Default: 0.0.")
    parser.add_argument("--out-file", default=str(DEFAULT_OUTPUT), help="Output Excel workbook.")
    parser.add_argument("--gaspar-out-file", default=None, help="Optional Gaspar workbook. Default derives a sibling file next to --out-file using a _gaspar_check name.")
    parser.add_argument("--combined-out-file", default=None, help=argparse.SUPPRESS)
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    points_file = Path(args.points_file)
    lau_file = Path(args.lau_file)
    events_file = Path(args.events_file)
    flood_dir = Path(args.flood_dir)
    france_lookup_file = Path(args.france_lookup_file) if args.france_lookup_file else None
    gaspar_file = Path(args.gaspar_file) if args.gaspar_file else None
    france_old_insee_updates_file = (
        Path(args.france_old_insee_updates_file) if args.france_old_insee_updates_file else None
    )
    tri_archive = Path(args.tri_archive) if args.tri_archive else None
    riparian_root = Path(args.riparian_root) if args.riparian_root else None
    out_file = Path(args.out_file)
    gaspar_out_value = args.gaspar_out_file or args.combined_out_file
    gaspar_out_file = (
        Path(gaspar_out_value)
        if gaspar_out_value
        else derive_gaspar_output_path(out_file)
    )

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

    print("Mapping points to LAU...")
    points_gdf = build_points_gdf(points_df, point_columns)
    points_with_lau = map_points_to_lau(points_gdf, lau_gdf)
    points_with_lau = attach_france_lookup(points_with_lau, france_lookup_file)
    points_with_lau["insee_com_key"] = normalize_insee_code_series(points_with_lau.get("insee_com"))

    target_lau_codes = {
        code
        for code in points_with_lau["lau_code"].dropna().astype(str).str.strip().tolist()
        if code
    }
    print(f"{len(target_lau_codes):,} unique LAU codes found under the supplied points.")

    print("Loading processed LAU event table...")
    event_df = load_lau_events(events_file, target_lau_codes)
    event_df = filter_events_by_study_period(
        event_df,
        study_start=args.study_start,
        study_end=args.study_end,
    )
    print(f"Loaded {len(event_df):,} candidate LAU-event rows for the mapped points.")

    point_key_cols = [point_columns.point_id, point_columns.latitude, point_columns.longitude, "excel_row_number", "geometry"]
    if point_columns.city and point_columns.city in points_with_lau.columns:
        point_key_cols.append(point_columns.city)
    mapping_cols = [
        "lau_code",
        "lau_code_local",
        "lau_name",
        "country_code",
        "population_2024",
        "area_km2",
        "insee_com",
        "commune_name_adminexpress",
        "insee_dep",
        "insee_reg",
        "nuts3_code",
        "nuts3_name",
    ]
    mapping_cols = [column for column in mapping_cols if column in points_with_lau.columns]
    point_extra_cols: list[str] = []
    if row_study_period_columns:
        for raw_col in [
            row_study_period_columns.anchor,
            row_study_period_columns.primary_end,
            row_study_period_columns.fallback_end,
        ]:
            if raw_col and raw_col in points_with_lau.columns and raw_col not in point_extra_cols:
                point_extra_cols.append(raw_col)
    for derived_col in ROW_STUDY_PERIOD_OUTPUT_COLUMNS:
        if derived_col in points_with_lau.columns and derived_col not in point_extra_cols:
            point_extra_cols.append(derived_col)
    point_base = points_with_lau[point_key_cols + mapping_cols + point_extra_cols].copy()

    candidate_df_all = point_base.merge(event_df, on="lau_code", how="left", suffixes=("", "_event"))

    candidate_df = filter_candidate_events_by_row_study_period(candidate_df_all)
    candidate_df = resolve_raster_paths(candidate_df, flood_dir=flood_dir)

    default_date_candidate_df = pd.DataFrame(columns=candidate_df_all.columns)
    if "study_period_anchor_date" in candidate_df_all.columns:
        default_date_candidate_df = filter_candidate_events_by_interval_columns(
            candidate_df_all,
            start_col=None,
            end_col="study_period_anchor_date",
        )
        default_date_candidate_df = resolve_raster_paths(default_date_candidate_df, flood_dir=flood_dir)

    print("Inspecting exact pixels and local buffers only for candidate events...")
    inspected_df = inspect_candidate_events(
        candidate_df=candidate_df,
        point_columns=point_columns,
        point_buffer_m=args.point_buffer_m,
        surrounding_buffer_km=args.buffer_km,
        threshold_cm=args.threshold_cm,
    )
    default_date_inspected_df = inspect_candidate_events(
        candidate_df=default_date_candidate_df,
        point_columns=point_columns,
        point_buffer_m=args.point_buffer_m,
        surrounding_buffer_km=args.buffer_km,
        threshold_cm=args.threshold_cm,
    )

    gaspar_candidate_df = pd.DataFrame()
    tri_classification_df = pd.DataFrame()
    gaspar_fallback_enabled = not args.disable_gaspar_fallback
    if gaspar_fallback_enabled:
        required_gaspar_paths = [
            gaspar_file,
            france_lookup_file,
            france_old_insee_updates_file,
            tri_archive,
        ]
        if any(path is None or not path.exists() for path in required_gaspar_paths):
            print("Gaspar fallback disabled at runtime because one or more required files are missing.")
        else:
            if riparian_root is None or not riparian_root.exists():
                print("Riparian root not found. Riparian fallback checks will stay negative.")
            print("Loading Gaspar commune events for fallback flag logic...")
            target_insee_codes = {
                code
                for code in points_with_lau["insee_com_key"].dropna().astype(str).str.strip().tolist()
                if code
            }
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
            gaspar_candidate_df = build_gaspar_candidate_events(
                points_with_lau=points_with_lau,
                point_columns=point_columns,
                gaspar_events_df=gaspar_events_df,
                row_study_period_columns=row_study_period_columns,
            )
            print("Classifying points against national TRI flood-risk polygons...")
            tri_classification_df = classify_points_against_tri(
                points_gdf=points_gdf,
                point_columns=point_columns,
                tri_archive=tri_archive,
                riparian_root=riparian_root,
            )

    print("Building summary tables...")
    summary_df = build_summary_table(
        original_points=points_df,
        point_columns=point_columns,
        points_with_lau=pd.DataFrame(points_with_lau.drop(columns="geometry", errors="ignore")),
        candidate_df=pd.DataFrame(candidate_df.drop(columns="geometry", errors="ignore")),
        inspected_df=inspected_df,
        default_date_inspected_df=default_date_inspected_df,
        point_buffer_m=args.point_buffer_m,
        surrounding_buffer_km=args.buffer_km,
        threshold_cm=args.threshold_cm,
        study_start=args.study_start,
        study_end=args.study_end,
    )
    candidate_sheet = build_candidate_sheet(
        candidate_df=pd.DataFrame(candidate_df.drop(columns="geometry", errors="ignore")),
        point_columns=point_columns,
        inspected_df=inspected_df,
        row_study_period_columns=row_study_period_columns,
    )
    hits_sheet = build_hits_sheet(candidate_sheet)
    jrc_hit_point_ids = set(
        summary_df.loc[
            summary_df["jrc_flood_hit"].fillna(False),
            point_columns.point_id,
        ].dropna()
    )
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
    gaspar_candidate_sheet = build_gaspar_candidate_sheet(
        gaspar_candidate_df=pd.DataFrame(gaspar_candidate_df.drop(columns="geometry", errors="ignore")),
        point_columns=point_columns,
        tri_classification_df=tri_classification_df,
        row_study_period_columns=row_study_period_columns,
    )
    gaspar_hits_sheet = build_gaspar_hits_sheet(gaspar_candidate_sheet)
    gaspar_hit_point_ids = set(gaspar_hits_sheet.get("point_id", pd.Series(dtype="object")).dropna().tolist())
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

    print("Writing JRC workbook...")
    write_output_workbook(
        output_path=out_file,
        point_flag_sheet=jrc_point_flag_sheet,
        detailed_sheet=jrc_detailed_sheet,
        candidate_sheet=candidate_sheet,
        hits_sheet=hits_sheet,
    )
    print("Writing Gaspar workbook...")
    write_gaspar_output_workbook(
        output_path=gaspar_out_file,
        point_flag_sheet=gaspar_point_flag_sheet,
        detailed_sheet=gaspar_detailed_sheet,
        candidate_sheet=gaspar_candidate_sheet,
        hits_sheet=gaspar_hits_sheet,
    )

    print("Done.")
    print(f"JRC workbook: {out_file.resolve()}")
    print(f"Gaspar workbook: {gaspar_out_file.resolve()}")
    print(
        {
            "n_points": int(len(summary_df)),
            "n_jrc_points_flagged": int(jrc_point_flag_sheet["flag_flood"].sum()),
            "n_candidate_event_rows": int(len(candidate_sheet)),
            "n_positive_event_hits": int(len(hits_sheet)),
            "n_gaspar_points_flagged": int(gaspar_point_flag_sheet["flag_flood"].sum()),
            "n_gaspar_candidate_rows": int(len(gaspar_candidate_sheet)),
            "n_gaspar_event_hits": int(len(gaspar_hits_sheet)),
        }
    )


if __name__ == "__main__":
    main()
