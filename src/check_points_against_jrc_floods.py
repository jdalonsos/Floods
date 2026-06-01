from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.errors import WindowError
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import Point, mapping

from granular_tabularization import load_lau


PERMANENT_WATER_VALUE = 9999
DEFAULT_FRANCE_POINT_FILE = Path("data/raw/france_20_gps_google_maps.xlsx")
DEFAULT_EVENT_TABLE = Path("data/processed/_outputs_eurostat_full/events_lau_long.parquet")
DEFAULT_LAU_FILE = Path("data/raw/LAU_RG_01M_2024_4326.gpkg")
DEFAULT_FLOOD_DIR = Path("data/JRC_flood_depth_maps")
DEFAULT_FRANCE_LOOKUP = Path("data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv")
DEFAULT_OUTPUT = Path("data/processed/france_points_jrc_flood_check.xlsx")
DEFAULT_POINT_BUFFER_M = 40.0
DEFAULT_SURROUNDING_BUFFER_KM = 1.0

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
) -> pd.DataFrame:
    """Keep only JRC events whose date interval overlaps the supplied row-level interval columns."""
    if candidate_df.empty:
        return candidate_df
    if (not start_col or start_col not in candidate_df.columns) and (not end_col or end_col not in candidate_df.columns):
        return candidate_df

    result = candidate_df.copy()
    overlap_mask = pd.Series(True, index=result.index)

    # A candidate event is kept when the event interval [start_date, end_date]
    # overlaps the chosen row-specific study interval [start_col, end_col].
    if start_col and start_col in result.columns:
        overlap_mask &= result[start_col].isna() | result["end_date"].ge(result[start_col])
    if end_col and end_col in result.columns:
        overlap_mask &= result[end_col].isna() | result["start_date"].le(result[end_col])

    keep_mask = result["event_id"].isna() | overlap_mask.fillna(False)
    return result[keep_mask].copy()


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


def empty_buffer_stats(prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_flood_hit": False,
        f"{prefix}_flooded_pixels": 0,
        f"{prefix}_flooded_area_m2": 0.0,
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

    valid = inside.copy()
    if np.ma.isMaskedArray(data):
        valid &= ~np.asarray(data.mask)
    if src.nodata is not None:
        valid &= arr != src.nodata
    valid &= arr != PERMANENT_WATER_VALUE
    valid &= arr > threshold_cm

    if not valid.any():
        return empty_buffer_stats(prefix)

    values = arr[valid].astype(float)
    flooded_pixels = int(values.size)
    pixel_area_m2 = abs(src.res[0] * src.res[1])
    return {
        f"{prefix}_flood_hit": True,
        f"{prefix}_flooded_pixels": flooded_pixels,
        f"{prefix}_flooded_area_m2": float(flooded_pixels * pixel_area_m2),
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
                "point_buffer_flood_hit",
                "point_buffer_flooded_pixels",
                "point_buffer_flooded_area_m2",
                "point_buffer_max_depth_cm",
                "point_buffer_median_depth_cm",
                "point_buffer_mean_depth_cm",
                "point_buffer_radius_m",
                "buffer_flood_hit",
                "buffer_flooded_pixels",
                "buffer_flooded_area_m2",
                "buffer_max_depth_cm",
                "buffer_median_depth_cm",
                "buffer_mean_depth_cm",
                "buffer_radius_km",
                "surrounding_buffer_flood_hit",
                "surrounding_buffer_flooded_pixels",
                "surrounding_buffer_flooded_area_m2",
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
                        "buffer_flood_hit": surrounding_buffer_stats["surrounding_buffer_flood_hit"],
                        "buffer_flooded_pixels": surrounding_buffer_stats["surrounding_buffer_flooded_pixels"],
                        "buffer_flooded_area_m2": surrounding_buffer_stats["surrounding_buffer_flooded_area_m2"],
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
) -> pd.DataFrame:
    summary = original_points.copy()
    point_id_col = point_columns.point_id
    inspected_df = inspected_df.copy()
    default_date_inspected_df = (
        default_date_inspected_df.copy() if default_date_inspected_df is not None else pd.DataFrame()
    )

    expected_inspected_columns: dict[str, Any] = {
        "point_buffer_flood_hit": False,
        "point_buffer_flooded_pixels": 0,
        "point_buffer_flooded_area_m2": 0.0,
        "point_buffer_max_depth_cm": np.nan,
        "point_buffer_median_depth_cm": np.nan,
        "point_buffer_mean_depth_cm": np.nan,
        "surrounding_buffer_flood_hit": False,
        "surrounding_buffer_flooded_pixels": 0,
        "surrounding_buffer_flooded_area_m2": 0.0,
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

    return summary


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
        "point_buffer_flood_hit": False,
        "point_buffer_flooded_pixels": 0,
        "point_buffer_flooded_area_m2": 0.0,
        "point_buffer_max_depth_cm": np.nan,
        "point_buffer_median_depth_cm": np.nan,
        "point_buffer_mean_depth_cm": np.nan,
        "point_buffer_radius_m": np.nan,
        "buffer_flood_hit": False,
        "buffer_flooded_pixels": 0,
        "buffer_flooded_area_m2": 0.0,
        "buffer_max_depth_cm": np.nan,
        "buffer_median_depth_cm": np.nan,
        "buffer_mean_depth_cm": np.nan,
        "buffer_radius_km": np.nan,
        "surrounding_buffer_flood_hit": False,
        "surrounding_buffer_flooded_pixels": 0,
        "surrounding_buffer_flooded_area_m2": 0.0,
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
        "point_buffer_flood_hit",
        "point_buffer_flooded_pixels",
        "point_buffer_flooded_area_m2",
        "point_buffer_max_depth_cm",
        "point_buffer_median_depth_cm",
        "point_buffer_mean_depth_cm",
        "point_buffer_radius_m",
        "buffer_flood_hit",
        "buffer_flooded_pixels",
        "buffer_flooded_area_m2",
        "buffer_max_depth_cm",
        "buffer_median_depth_cm",
        "buffer_mean_depth_cm",
        "buffer_radius_km",
        "surrounding_buffer_flood_hit",
        "surrounding_buffer_flooded_pixels",
        "surrounding_buffer_flooded_area_m2",
        "surrounding_buffer_max_depth_cm",
        "surrounding_buffer_median_depth_cm",
        "surrounding_buffer_mean_depth_cm",
        "surrounding_buffer_radius_km",
    ]
    available = [column for column in ordered_cols if column in candidate_only.columns]
    remainder = [column for column in candidate_only.columns if column not in available]
    return candidate_only[available + remainder].sort_values(["point_id", "start_date", "event_id"]).copy()


def build_hits_sheet(candidate_sheet: pd.DataFrame) -> pd.DataFrame:
    if candidate_sheet.empty:
        return candidate_sheet
    if "surrounding_buffer_flood_hit" not in candidate_sheet.columns:
        candidate_sheet = candidate_sheet.copy()
        candidate_sheet["surrounding_buffer_flood_hit"] = candidate_sheet.get("buffer_flood_hit", False)
    if "point_buffer_flood_hit" not in candidate_sheet.columns:
        candidate_sheet = candidate_sheet.copy()
        candidate_sheet["point_buffer_flood_hit"] = candidate_sheet.get("hit_at_point", False)
    return candidate_sheet[
        candidate_sheet["surrounding_buffer_flood_hit"].fillna(False)
        | candidate_sheet["point_buffer_flood_hit"].fillna(False)
    ].copy()


def write_output_workbook(
    output_path: Path,
    summary_df: pd.DataFrame,
    candidate_sheet: pd.DataFrame,
    hits_sheet: pd.DataFrame,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="point_summary", index=False)
        candidate_sheet.to_excel(writer, sheet_name="candidate_events", index=False)
        hits_sheet.to_excel(writer, sheet_name="event_hits", index=False)


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
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    points_file = Path(args.points_file)
    lau_file = Path(args.lau_file)
    events_file = Path(args.events_file)
    flood_dir = Path(args.flood_dir)
    france_lookup_file = Path(args.france_lookup_file) if args.france_lookup_file else None
    out_file = Path(args.out_file)

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

    print("Writing workbook...")
    write_output_workbook(
        output_path=out_file,
        summary_df=summary_df,
        candidate_sheet=candidate_sheet,
        hits_sheet=hits_sheet,
    )

    print("Done.")
    print(f"Output workbook: {out_file.resolve()}")
    print(
        {
            "n_points": int(len(summary_df)),
            "n_points_with_lau": int(summary_df["lau_matched"].sum()),
            "n_points_with_candidate_events": int(summary_df["lau_touched_by_any_jrc_event"].sum()),
            "n_points_with_positive_hit": int(summary_df["jrc_flood_hit"].sum()),
            "n_candidate_event_rows": int(len(candidate_sheet)),
            "n_positive_event_hits": int(len(hits_sheet)),
        }
    )


if __name__ == "__main__":
    main()
