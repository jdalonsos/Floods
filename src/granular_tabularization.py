"""
Event-based tabularisation of European flood depth maps using Eurostat LAU + NUTS.

Design principles for this version:
- treat each official JRC flood raster as exactly one event
- accept only filenames that match the official README F02 convention exactly
- reject derived display files such as *_3857_60m_cog.tif automatically
- use a single mapping source family across Europe: Eurostat LAU + NUTS
- enrich every LAU with NUTS0/1/2/3
- write outputs for LAU and every NUTS level

The long LAU output is the canonical table. Higher levels are deterministic
aggregations of that table.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import CRS as PyprojCRS
from rasterio.crs import CRS
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import box


OFFICIAL_FILENAME_RE = re.compile(
    r"^WD_MERGE_"
    r"(?P<start_date>\d{4}-\d{2}-\d{2})---(?P<end_date>\d{4}-\d{2}-\d{2})"
    r"_duration_(?P<duration_days>\d+)_days"
    r"_cluster_(?P<flood_id>\d+)"
    r"_A0_(?P<gfm_extent_km2>\d+)"
    r"_A_(?P<enhanced_extent_km2>\d+)"
    r"_lat_(?P<centroid_lat_cents>-?\d+)"
    r"_lon_(?P<centroid_lon_cents>-?\d+)"
    r"_size_(?P<spatial_spread_units>\d+)"
    r"\.(?:tif|tiff)$",
    flags=re.IGNORECASE,
)

YEAR_DIR_RE = re.compile(r"^(?P<year>\d{4})(?:_filtered)?$")
EXCEL_ROW_LIMIT = 1_000_000
OFFICIAL_RASTER_CRS = PyprojCRS.from_epsg(27704)
COUNTRY_NAME_FALLBACKS = {
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "EL": "Greece",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IS": "Iceland",
    "IT": "Italy",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "MT": "Malta",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "TR": "Turkey",
    "UK": "United Kingdom",
    "XK": "Kosovo",
}

EVENT_META_COLUMNS = [
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
]

LOOKUP_COLUMNS = [
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

LAU_OUTPUT_COLUMNS = EVENT_META_COLUMNS + [
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

SUMMARY_COLUMNS = EVENT_META_COLUMNS + [
    "raster_crs",
    "raster_dtype",
    "raster_nodata",
    "pixel_size_x",
    "pixel_size_y",
    "pixel_area_m2",
    "raster_width",
    "raster_height",
    "n_candidate_lau",
    "n_lau_flooded",
    "n_nuts0_flooded",
    "n_nuts1_flooded",
    "n_nuts2_flooded",
    "n_nuts3_flooded",
]


@dataclass(frozen=True)
class FloodEvent:
    event_id: str
    raster_path: Path
    raster_file: str
    source_year_folder: Optional[int]
    start_date: str
    end_date: str
    duration_days: int
    flood_id: int
    gfm_extent_km2: int
    enhanced_extent_km2: int
    centroid_lat_cents: int
    centroid_lon_cents: int
    spatial_spread_units: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "raster_file": self.raster_file,
            "raster_path": str(self.raster_path),
            "source_year_folder": self.source_year_folder,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "duration_days": self.duration_days,
            "flood_id": self.flood_id,
            "gfm_extent_km2": self.gfm_extent_km2,
            "enhanced_extent_km2": self.enhanced_extent_km2,
            "centroid_lat_cents": self.centroid_lat_cents,
            "centroid_lon_cents": self.centroid_lon_cents,
            "spatial_spread_units": self.spatial_spread_units,
        }


@dataclass
class ProjectedAdmin:
    gdf: gpd.GeoDataFrame

    @property
    def sindex(self) -> Any:
        return self.gdf.sindex


class AdminCache:
    """Cache reprojected LAU geometries by raster CRS."""

    def __init__(self, lau_gdf: gpd.GeoDataFrame) -> None:
        self._base = lau_gdf
        self._cache: Dict[str, ProjectedAdmin] = {}

    def get(self, crs: CRS) -> ProjectedAdmin:
        key = crs.to_wkt() if crs else "<missing>"
        if key not in self._cache:
            projected = self._base.to_crs(crs).copy()
            projected = clean_geometries(projected)
            self._cache[key] = ProjectedAdmin(projected)
        return self._cache[key]


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cleaned = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    try:
        cleaned["geometry"] = cleaned.geometry.make_valid()
    except Exception:
        cleaned["geometry"] = cleaned.geometry.buffer(0)
    cleaned = cleaned[cleaned.geometry.notna() & ~cleaned.geometry.is_empty].copy()
    return cleaned


def infer_year_from_path(path: Path) -> Optional[int]:
    for part in path.parts:
        match = YEAR_DIR_RE.match(part)
        if match:
            return int(match.group("year"))
    return None


def parse_event_from_filename(filename: str) -> Optional[FloodEvent]:
    match = OFFICIAL_FILENAME_RE.match(filename)
    if not match:
        return None

    meta = match.groupdict()
    return FloodEvent(
        event_id=Path(filename).stem,
        raster_path=Path("."),
        raster_file=filename,
        source_year_folder=None,
        start_date=meta["start_date"],
        end_date=meta["end_date"],
        duration_days=int(meta["duration_days"]),
        flood_id=int(meta["flood_id"]),
        gfm_extent_km2=int(meta["gfm_extent_km2"]),
        enhanced_extent_km2=int(meta["enhanced_extent_km2"]),
        centroid_lat_cents=int(meta["centroid_lat_cents"]),
        centroid_lon_cents=int(meta["centroid_lon_cents"]),
        spatial_spread_units=int(meta["spatial_spread_units"]),
    )


def event_from_path(path: Path) -> Optional[FloodEvent]:
    parsed = parse_event_from_filename(path.name)
    if parsed is None:
        return None
    return FloodEvent(
        event_id=parsed.event_id,
        raster_path=path.resolve(),
        raster_file=path.name,
        source_year_folder=infer_year_from_path(path),
        start_date=parsed.start_date,
        end_date=parsed.end_date,
        duration_days=parsed.duration_days,
        flood_id=parsed.flood_id,
        gfm_extent_km2=parsed.gfm_extent_km2,
        enhanced_extent_km2=parsed.enhanced_extent_km2,
        centroid_lat_cents=parsed.centroid_lat_cents,
        centroid_lon_cents=parsed.centroid_lon_cents,
        spatial_spread_units=parsed.spatial_spread_units,
    )


def discover_flood_events(
    flood_dir: str | Path,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    max_files: Optional[int] = None,
) -> tuple[list[FloodEvent], dict[str, Any]]:
    root = Path(flood_dir)
    if not root.exists():
        raise FileNotFoundError(f"Flood directory not found: {root}")

    year_dirs = [
        p for p in sorted(root.iterdir()) if p.is_dir() and YEAR_DIR_RE.match(p.name)
    ]

    if year_dirs:
        candidate_dirs = []
        for year_dir in year_dirs:
            year = infer_year_from_path(year_dir)
            if year_from is not None and year is not None and year < year_from:
                continue
            if year_to is not None and year is not None and year > year_to:
                continue
            candidate_dirs.append(year_dir)
    else:
        candidate_dirs = [root]

    all_seen = 0
    accepted = 0
    rejected_non_official = 0
    duplicate_event_ids = 0
    duplicate_examples: list[dict[str, str]] = []

    events_by_id: dict[str, FloodEvent] = {}

    for directory in candidate_dirs:
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".tif", ".tiff"}:
                continue

            all_seen += 1
            event = event_from_path(path)
            if event is None:
                rejected_non_official += 1
                continue

            if event.event_id in events_by_id:
                duplicate_event_ids += 1
                if len(duplicate_examples) < 20:
                    duplicate_examples.append(
                        {
                            "event_id": event.event_id,
                            "kept": str(events_by_id[event.event_id].raster_path),
                            "skipped": str(event.raster_path),
                        }
                    )
                continue

            events_by_id[event.event_id] = event
            accepted += 1

    events = sorted(events_by_id.values(), key=lambda e: e.raster_file)
    if max_files is not None and max_files > 0:
        events = events[:max_files]

    inventory = {
        "root": str(root.resolve()),
        "candidate_directories": [str(p.resolve()) for p in candidate_dirs],
        "all_tif_seen": all_seen,
        "accepted_official_event_files": accepted,
        "rejected_non_official_tif": rejected_non_official,
        "duplicate_event_ids_skipped": duplicate_event_ids,
        "duplicate_examples": duplicate_examples,
        "events_selected_after_limit": len(events),
    }
    return events, inventory


def load_lau(
    lau_path: str | Path,
    target_countries: Optional[set[str]] = None,
) -> gpd.GeoDataFrame:
    lau_gdf = gpd.read_file(lau_path)
    columns = set(lau_gdf.columns)

    if {"GISCO_ID", "CNTR_CODE", "LAU_NAME"}.issubset(columns):
        lau_gdf = lau_gdf.rename(
            columns={
                "GISCO_ID": "lau_code",
                "CNTR_CODE": "country_code",
                "LAU_NAME": "lau_name",
                "POP_2024": "population_2024",
                "AREA_KM2": "area_km2",
            }
        )
    elif {"lau_code", "country_code", "lau_name"}.issubset(columns):
        pass
    else:
        raise KeyError(
            "Unsupported LAU schema. Expected official Eurostat columns "
            "GISCO_ID/CNTR_CODE/LAU_NAME."
        )

    if lau_gdf.crs is None:
        raise ValueError("LAU dataset has no CRS.")
    if lau_gdf.crs.to_epsg() != 4326:
        lau_gdf = lau_gdf.to_crs(4326)

    lau_gdf["lau_code"] = lau_gdf["lau_code"].astype(str).str.strip()
    lau_gdf["lau_name"] = lau_gdf["lau_name"].astype(str).str.strip()
    lau_gdf["country_code"] = lau_gdf["country_code"].astype(str).str.strip()
    lau_gdf["lau_code_local"] = lau_gdf["lau_code"].str.replace(r"^[A-Z]{2}_", "", regex=True)

    if target_countries:
        lau_gdf = lau_gdf[lau_gdf["country_code"].isin(target_countries)].copy()

    keep_cols = [
        "lau_code",
        "lau_code_local",
        "lau_name",
        "country_code",
        "geometry",
    ]
    for optional_col in ["population_2024", "area_km2"]:
        if optional_col in lau_gdf.columns:
            keep_cols.append(optional_col)

    lau_gdf = lau_gdf[keep_cols].copy()
    lau_gdf = clean_geometries(lau_gdf)

    if lau_gdf["lau_code"].duplicated().any():
        duplicates = (
            lau_gdf.loc[lau_gdf["lau_code"].duplicated(keep=False), "lau_code"]
            .sort_values()
            .unique()
            .tolist()
        )
        raise ValueError(
            "LAU codes are not unique. Sample duplicates: "
            f"{duplicates[:10]}"
        )

    return lau_gdf


def load_nuts(
    nuts_path: str | Path,
    target_countries: Optional[set[str]] = None,
) -> gpd.GeoDataFrame:
    nuts_gdf = gpd.read_file(nuts_path)
    required = {"LEVL_CODE", "NUTS_ID", "NUTS_NAME", "CNTR_CODE", "geometry"}
    if not required.issubset(nuts_gdf.columns):
        raise KeyError(
            "Unsupported NUTS schema. Expected official Eurostat columns "
            "LEVL_CODE/NUTS_ID/NUTS_NAME/CNTR_CODE."
        )

    if nuts_gdf.crs is None:
        raise ValueError("NUTS dataset has no CRS.")
    if nuts_gdf.crs.to_epsg() != 4326:
        nuts_gdf = nuts_gdf.to_crs(4326)

    nuts_gdf = nuts_gdf[nuts_gdf["LEVL_CODE"].isin([0, 1, 2, 3])].copy()
    nuts_gdf["CNTR_CODE"] = nuts_gdf["CNTR_CODE"].astype(str).str.strip()

    if target_countries:
        nuts_gdf = nuts_gdf[nuts_gdf["CNTR_CODE"].isin(target_countries)].copy()

    nuts_gdf = clean_geometries(nuts_gdf)
    return nuts_gdf


def join_level_by_point(
    points_gdf: gpd.GeoDataFrame,
    level_gdf: gpd.GeoDataFrame,
    code_col: str,
    name_col: str,
) -> pd.DataFrame:
    joined = gpd.sjoin(
        points_gdf,
        level_gdf[[code_col, name_col, "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")

    missing = joined[code_col].isna()
    if missing.any():
        fallback = gpd.sjoin(
            points_gdf.loc[missing],
            level_gdf[[code_col, name_col, "geometry"]],
            how="left",
            predicate="intersects",
        ).drop(columns=["index_right"], errors="ignore")
        fallback = fallback[~fallback.index.duplicated(keep="first")]
        joined.loc[fallback.index, code_col] = fallback[code_col]
        joined.loc[fallback.index, name_col] = fallback[name_col]

    return joined[["lau_code", code_col, name_col]].drop_duplicates(subset=["lau_code"])


def enrich_lau_with_nuts(
    lau_gdf: gpd.GeoDataFrame,
    nuts_gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    enriched = lau_gdf.copy()
    lau_points = enriched[["lau_code", "geometry"]].copy()
    lau_points["geometry"] = lau_points.geometry.representative_point()
    lau_points = gpd.GeoDataFrame(lau_points, geometry="geometry", crs=enriched.crs)

    diagnostics: dict[str, int] = {}

    for level in range(4):
        level_gdf = nuts_gdf[nuts_gdf["LEVL_CODE"] == level].copy()
        code_col = f"nuts{level}_code"
        name_col = f"nuts{level}_name"
        level_gdf = level_gdf.rename(
            columns={
                "NUTS_ID": code_col,
                "NUTS_NAME": name_col,
            }
        )
        level_match = join_level_by_point(lau_points, level_gdf, code_col, name_col)
        enriched = enriched.merge(level_match, on="lau_code", how="left")
        diagnostics[f"missing_{code_col}"] = int(enriched[code_col].isna().sum())

    enriched["nuts0_code"] = enriched["nuts0_code"].fillna(enriched["country_code"])
    enriched["nuts0_name"] = enriched["nuts0_name"].fillna(
        enriched["country_code"].map(COUNTRY_NAME_FALLBACKS)
    ).fillna(enriched["country_code"])
    enriched["country_name"] = enriched["nuts0_name"].fillna(enriched["country_code"])
    diagnostics["missing_nuts0_code"] = int(enriched["nuts0_code"].isna().sum())

    for optional_col in ["population_2024", "area_km2"]:
        if optional_col not in enriched.columns:
            enriched[optional_col] = np.nan

    return enriched, diagnostics


def validate_raster_specs(src: rasterio.io.DatasetReader, event: FloodEvent) -> None:
    if src.crs is None:
        raise ValueError(f"Raster has no CRS: {event.raster_file}")

    crs_text = src.crs.to_wkt().lower()
    matches_official_crs = False
    try:
        matches_official_crs = PyprojCRS.from_wkt(src.crs.to_wkt()) == OFFICIAL_RASTER_CRS
    except Exception:
        matches_official_crs = False

    if not matches_official_crs and (
        "azimuthal" not in crs_text or "equidistant" not in crs_text
    ):
        raise ValueError(
            "Raster CRS does not match the official Europe Equi7 / "
            f"Azimuthal Equidistant flood grid: {event.raster_file}"
        )

    if src.dtypes[0].lower() != "uint16":
        raise ValueError(
            f"Raster dtype is not uint16: {event.raster_file} ({src.dtypes[0]})"
        )

    if not np.isclose(abs(src.res[0]), 20.0) or not np.isclose(abs(src.res[1]), 20.0):
        raise ValueError(
            f"Raster resolution is not 20m: {event.raster_file} ({src.res})"
        )


def compute_event_lau_stats(
    event: FloodEvent,
    admin_cache: AdminCache,
    threshold_cm: float = 0.0,
    all_touched: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    with rasterio.open(event.raster_path) as src:
        validate_raster_specs(src, event)

        pixel_area_m2 = float(abs(src.transform.a) * abs(src.transform.e))
        projected = admin_cache.get(src.crs)

        candidate_idx = list(projected.sindex.intersection(src.bounds))
        if not candidate_idx:
            return (
                pd.DataFrame(columns=LAU_OUTPUT_COLUMNS),
                {
                    **event.to_dict(),
                    "raster_crs": src.crs.to_string(),
                    "raster_dtype": src.dtypes[0],
                    "raster_nodata": src.nodata,
                    "pixel_size_x": float(src.res[0]),
                    "pixel_size_y": float(src.res[1]),
                    "pixel_area_m2": pixel_area_m2,
                    "raster_width": int(src.width),
                    "raster_height": int(src.height),
                    "n_candidate_lau": 0,
                    "n_lau_flooded": 0,
                    "n_nuts0_flooded": 0,
                    "n_nuts1_flooded": 0,
                    "n_nuts2_flooded": 0,
                    "n_nuts3_flooded": 0,
                },
            )

        raster_box = box(*src.bounds)
        candidates = projected.gdf.iloc[candidate_idx].copy()
        candidates = candidates[candidates.intersects(raster_box)].copy()

        records: list[dict[str, Any]] = []

        for _, row in candidates.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue

            try:
                window = geometry_window(src, [geom], pad_x=0, pad_y=0)
            except Exception:
                continue

            data = src.read(1, window=window, masked=False)
            if data.size == 0:
                continue

            window_transform = src.window_transform(window)
            outside_mask = geometry_mask(
                [geom],
                out_shape=data.shape,
                transform=window_transform,
                invert=False,
                all_touched=all_touched,
            )

            final_mask = outside_mask.copy()
            if src.nodata is not None:
                final_mask |= data == src.nodata
            final_mask |= data == 9999

            masked = np.ma.masked_array(data, mask=final_mask)
            if masked.count() == 0:
                continue

            values = masked.compressed().astype(np.float32, copy=False)
            flooded_values = values[values > threshold_cm]
            if flooded_values.size == 0:
                continue

            record = {col: row[col] for col in LOOKUP_COLUMNS if col in row.index}
            record["max_depth_cm"] = float(flooded_values.max())
            record["flooded_pixels"] = int(flooded_values.size)
            record["flooded_area_m2"] = float(flooded_values.size * pixel_area_m2)
            records.append(record)

        event_df = pd.DataFrame(records)
        if event_df.empty:
            summary = {
                **event.to_dict(),
                "raster_crs": src.crs.to_string(),
                "raster_dtype": src.dtypes[0],
                "raster_nodata": src.nodata,
                "pixel_size_x": float(src.res[0]),
                "pixel_size_y": float(src.res[1]),
                "pixel_area_m2": pixel_area_m2,
                "raster_width": int(src.width),
                "raster_height": int(src.height),
                "n_candidate_lau": int(len(candidates)),
                "n_lau_flooded": 0,
                "n_nuts0_flooded": 0,
                "n_nuts1_flooded": 0,
                "n_nuts2_flooded": 0,
                "n_nuts3_flooded": 0,
            }
            return pd.DataFrame(columns=LAU_OUTPUT_COLUMNS), summary

        for key, value in event.to_dict().items():
            event_df[key] = value

        event_df = event_df[LAU_OUTPUT_COLUMNS].copy()

        summary = {
            **event.to_dict(),
            "raster_crs": src.crs.to_string(),
            "raster_dtype": src.dtypes[0],
            "raster_nodata": src.nodata,
            "pixel_size_x": float(src.res[0]),
            "pixel_size_y": float(src.res[1]),
            "pixel_area_m2": pixel_area_m2,
            "raster_width": int(src.width),
            "raster_height": int(src.height),
            "n_candidate_lau": int(len(candidates)),
            "n_lau_flooded": int(event_df["lau_code"].nunique()),
            "n_nuts0_flooded": int(event_df["nuts0_code"].dropna().nunique()),
            "n_nuts1_flooded": int(event_df["nuts1_code"].dropna().nunique()),
            "n_nuts2_flooded": int(event_df["nuts2_code"].dropna().nunique()),
            "n_nuts3_flooded": int(event_df["nuts3_code"].dropna().nunique()),
        }
        return event_df, summary


def aggregate_level(lau_df: pd.DataFrame, level: int) -> pd.DataFrame:
    if level == 0:
        level_cols = ["nuts0_code", "nuts0_name"]
    elif level == 1:
        level_cols = ["nuts0_code", "nuts0_name", "nuts1_code", "nuts1_name"]
    elif level == 2:
        level_cols = [
            "nuts0_code",
            "nuts0_name",
            "nuts1_code",
            "nuts1_name",
            "nuts2_code",
            "nuts2_name",
        ]
    elif level == 3:
        level_cols = [
            "nuts0_code",
            "nuts0_name",
            "nuts1_code",
            "nuts1_name",
            "nuts2_code",
            "nuts2_name",
            "nuts3_code",
            "nuts3_name",
        ]
    else:
        raise ValueError(f"Unsupported NUTS level: {level}")

    df = lau_df.dropna(subset=[level_cols[-2]]).copy()
    if df.empty:
        return pd.DataFrame(
            columns=EVENT_META_COLUMNS
            + level_cols
            + ["max_depth_cm", "flooded_pixels", "flooded_area_m2", "n_lau"]
        )

    group_cols = EVENT_META_COLUMNS + level_cols
    aggregated = (
        df.groupby(group_cols, dropna=False)
        .agg(
            max_depth_cm=("max_depth_cm", "max"),
            flooded_pixels=("flooded_pixels", "sum"),
            flooded_area_m2=("flooded_area_m2", "sum"),
            n_lau=("lau_code", "nunique"),
        )
        .reset_index()
    )
    return aggregated


def sort_outputs(
    lau_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not lau_df.empty:
        lau_df = lau_df.sort_values(
            ["start_date", "end_date", "flood_id", "lau_code"],
            na_position="last",
        ).reset_index(drop=True)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["start_date", "end_date", "flood_id"],
            na_position="last",
        ).reset_index(drop=True)
    if not lookup_df.empty:
        lookup_df = lookup_df.sort_values(
            ["country_code", "lau_code"],
            na_position="last",
        ).reset_index(drop=True)
    return lau_df, summary_df, lookup_df


def write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def maybe_write_parquet(path: Path, df: pd.DataFrame) -> Optional[str]:
    try:
        df.to_parquet(path, index=False)
        return str(path)
    except Exception:
        return None


def write_excel_workbook(
    path: Path,
    tables: Sequence[tuple[str, pd.DataFrame]],
) -> dict[str, str]:
    status: dict[str, str] = {}
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, df in tables:
            if df.empty:
                status[sheet_name] = "empty"
                continue
            if len(df) > EXCEL_ROW_LIMIT:
                status[sheet_name] = f"skipped_rows_{len(df)}"
                continue
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            status[sheet_name] = f"written_rows_{len(df)}"
    return status


def write_outputs(
    out_dir: str | Path,
    lau_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    inventory: dict[str, Any],
    join_diagnostics: dict[str, int],
    config: dict[str, Any],
) -> dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    lau_df, summary_df, lookup_df = sort_outputs(lau_df, summary_df, lookup_df)
    nuts0_df = aggregate_level(lau_df, 0)
    nuts1_df = aggregate_level(lau_df, 1)
    nuts2_df = aggregate_level(lau_df, 2)
    nuts3_df = aggregate_level(lau_df, 3)

    write_csv(out_path / "events_lau_long.csv", lau_df)
    write_csv(out_path / "events_summary.csv", summary_df)
    write_csv(out_path / "lau_nuts_lookup.csv", lookup_df)
    write_csv(out_path / "events_nuts0.csv", nuts0_df)
    write_csv(out_path / "events_nuts1.csv", nuts1_df)
    write_csv(out_path / "events_nuts2.csv", nuts2_df)
    write_csv(out_path / "events_nuts3.csv", nuts3_df)

    parquet_paths = {
        "events_lau_long_parquet": maybe_write_parquet(out_path / "events_lau_long.parquet", lau_df),
        "events_summary_parquet": maybe_write_parquet(out_path / "events_summary.parquet", summary_df),
    }

    excel_status = write_excel_workbook(
        out_path / "flood_event_tables.xlsx",
        [
            ("events_summary", summary_df),
            ("events_lau_long", lau_df),
            ("events_nuts0", nuts0_df),
            ("events_nuts1", nuts1_df),
            ("events_nuts2", nuts2_df),
            ("events_nuts3", nuts3_df),
            ("lau_nuts_lookup", lookup_df),
        ],
    )

    run_metadata = {
        "config": config,
        "inventory": inventory,
        "join_diagnostics": join_diagnostics,
        "row_counts": {
            "events_lau_long": int(len(lau_df)),
            "events_summary": int(len(summary_df)),
            "events_nuts0": int(len(nuts0_df)),
            "events_nuts1": int(len(nuts1_df)),
            "events_nuts2": int(len(nuts2_df)),
            "events_nuts3": int(len(nuts3_df)),
            "lau_nuts_lookup": int(len(lookup_df)),
        },
        "parquet_outputs": parquet_paths,
        "excel_status": excel_status,
    }

    (out_path / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return run_metadata


def process_events(
    events: Sequence[FloodEvent],
    lau_gdf: gpd.GeoDataFrame,
    threshold_cm: float,
    all_touched: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    admin_cache = AdminCache(lau_gdf)
    lau_rows: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []

    total = len(events)
    for idx, event in enumerate(events, start=1):
        print(f"[{idx}/{total}] Processing {event.raster_file}")
        event_df, summary = compute_event_lau_stats(
            event=event,
            admin_cache=admin_cache,
            threshold_cm=threshold_cm,
            all_touched=all_touched,
        )
        summaries.append(summary)
        if not event_df.empty:
            lau_rows.append(event_df)

    lau_df = pd.concat(lau_rows, ignore_index=True) if lau_rows else pd.DataFrame(columns=LAU_OUTPUT_COLUMNS)
    summary_df = pd.DataFrame(summaries, columns=SUMMARY_COLUMNS)
    return lau_df, summary_df


def parse_country_filter(raw: Optional[str]) -> Optional[set[str]]:
    if raw is None or not raw.strip():
        return None
    values = {item.strip().upper() for item in raw.split(",") if item.strip()}
    return values or None


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Strict event-based tabularisation of official JRC flood rasters "
            "using Eurostat LAU + NUTS0/1/2/3."
        )
    )
    parser.add_argument("--lau", required=True, help="Path to the Eurostat LAU GeoPackage.")
    parser.add_argument("--nuts", required=True, help="Path to the Eurostat NUTS GeoPackage.")
    parser.add_argument(
        "--flood-dir",
        required=True,
        help=(
            "Directory containing official flood rasters. Can point to the raw year "
            "folders or a filtered tree; only official F02 filenames are accepted."
        ),
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for CSV, optional parquet, Excel workbook, and metadata.",
    )
    parser.add_argument("--year-from", type=int, default=None, help="Optional lower year bound.")
    parser.add_argument("--year-to", type=int, default=None, help="Optional upper year bound.")
    parser.add_argument(
        "--countries",
        default=None,
        help=(
            "Optional comma-separated ISO-like Eurostat country codes to keep, "
            "for example FR,BE,IT,LU."
        ),
    )
    parser.add_argument(
        "--threshold-cm",
        type=float,
        default=0.0,
        help="Minimum flood depth in cm to count a pixel as flooded. Default: 0.0.",
    )
    parser.add_argument(
        "--all-touched",
        action="store_true",
        help="Rasterize polygons with all_touched=True. Default is False for less boundary inflation.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Process at most this many accepted event rasters. Set 0 to process all.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    target_countries = parse_country_filter(args.countries)
    max_files = None if args.max_files <= 0 else args.max_files

    print("Loading Eurostat LAU...")
    lau_gdf = load_lau(args.lau, target_countries=target_countries)
    print(f"Loaded {len(lau_gdf):,} LAU polygons.")

    print("Loading Eurostat NUTS...")
    nuts_gdf = load_nuts(args.nuts, target_countries=target_countries)
    print(f"Loaded {len(nuts_gdf):,} NUTS polygons across levels 0-3.")

    print("Mapping LAU to NUTS0/1/2/3...")
    lau_enriched, join_diagnostics = enrich_lau_with_nuts(lau_gdf, nuts_gdf)
    print("Join diagnostics:", join_diagnostics)

    print("Discovering official event rasters...")
    events, inventory = discover_flood_events(
        flood_dir=args.flood_dir,
        year_from=args.year_from,
        year_to=args.year_to,
        max_files=max_files,
    )
    print("Inventory:", json.dumps(inventory, indent=2))

    if not events:
        raise RuntimeError("No official event rasters found after filtering.")

    print("Processing events...")
    lau_df, summary_df = process_events(
        events=events,
        lau_gdf=lau_enriched,
        threshold_cm=args.threshold_cm,
        all_touched=args.all_touched,
    )

    config = {
        "lau": str(Path(args.lau).resolve()),
        "nuts": str(Path(args.nuts).resolve()),
        "flood_dir": str(Path(args.flood_dir).resolve()),
        "out_dir": str(Path(args.out_dir).resolve()),
        "year_from": args.year_from,
        "year_to": args.year_to,
        "countries": sorted(target_countries) if target_countries else None,
        "threshold_cm": args.threshold_cm,
        "all_touched": args.all_touched,
        "max_files": max_files,
    }

    print("Writing outputs...")
    run_metadata = write_outputs(
        out_dir=args.out_dir,
        lau_df=lau_df,
        summary_df=summary_df,
        lookup_df=lau_enriched[LOOKUP_COLUMNS].drop_duplicates(subset=["lau_code"]).copy(),
        inventory=inventory,
        join_diagnostics=join_diagnostics,
        config=config,
    )

    print("Done.")
    print(json.dumps(run_metadata["row_counts"], indent=2))


if __name__ == "__main__":
    main()
