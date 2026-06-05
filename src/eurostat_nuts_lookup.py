from __future__ import annotations

from typing import Any, Optional

import geopandas as gpd
import numpy as np
import pandas as pd


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


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cleaned = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    try:
        cleaned["geometry"] = cleaned.geometry.make_valid()
    except Exception:
        cleaned["geometry"] = cleaned.geometry.buffer(0)
    cleaned = cleaned[cleaned.geometry.notna() & ~cleaned.geometry.is_empty].copy()
    return cleaned


def load_nuts(
    nuts_path: str,
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
