"""
Filter the Europe LAU flood table to France and map LAU rows to INSEE communes.

This script is designed to run after ``granular_tabularization.py``. It takes
the canonical ``events_lau_long`` output, keeps only France rows, and adds a
current AdminExpress commune code for downstream comparison with Gaspar or
other French national datasets.

Matching strategy:
- exact code match first: ``lau_code_local`` -> ``insee_com``
- spatial fallback second: France LAU representative point -> AdminExpress
  commune polygon using ``within``, then ``intersects`` if needed
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from eurostat_nuts_lookup import enrich_lau_with_nuts, load_nuts


FRANCE_LOOKUP_COLUMNS = [
    "lau_code",
    "lau_code_local",
    "lau_name_lau",
    "insee_com",
    "commune_name_adminexpress",
    "insee_dep",
    "insee_reg",
    "adminexpress_population",
    "adminexpress_statut",
    "nuts3_code",
    "nuts3_name",
    "match_type",
    "match_method",
    "insee_code_changed_from_lau",
]

FRANCE_OUTPUT_APPEND_COLUMNS = [
    "insee_com",
    "commune_name_adminexpress",
    "insee_dep",
    "insee_reg",
    "adminexpress_population",
    "adminexpress_statut",
    "nuts3_code",
    "nuts3_name",
    "match_type",
    "match_method",
    "insee_code_changed_from_lau",
]

OLD_TO_NEW_MAPPING_COLUMNS = [
    "old_insee_com",
    "old_commune_name",
    "old_date_debut",
    "old_date_fin",
    "new_insee_com",
    "new_commune_name",
    "new_lau_code",
    "new_lau_name",
    "new_nuts3_code",
    "new_nuts3_name",
    "new_insee_dep",
    "new_insee_reg",
    "current_match_count",
    "mapping_resolution",
    "update_ready",
    "insee_code_changed",
    "commune_name_changed",
]


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cleaned = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    try:
        cleaned["geometry"] = cleaned.geometry.make_valid()
    except Exception:
        cleaned["geometry"] = cleaned.geometry.buffer(0)
    cleaned = cleaned[cleaned.geometry.notna() & ~cleaned.geometry.is_empty].copy()
    return cleaned


def read_table(path: str | Path) -> pd.DataFrame:
    table_path = Path(path)
    suffix = table_path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(table_path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(table_path, low_memory=False)
    raise ValueError(f"Unsupported input format for {table_path}. Use CSV or parquet.")


def write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def read_insee_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("")


def load_france_lau(lau_path: str | Path) -> gpd.GeoDataFrame:
    lau_gdf = gpd.read_file(lau_path, where="CNTR_CODE = 'FR'")
    required = {"GISCO_ID", "CNTR_CODE", "LAU_NAME", "geometry"}
    if not required.issubset(lau_gdf.columns):
        raise KeyError(
            "Unsupported LAU schema. Expected official Eurostat columns "
            "GISCO_ID/CNTR_CODE/LAU_NAME."
        )

    if lau_gdf.crs is None:
        raise ValueError("LAU dataset has no CRS.")
    if lau_gdf.crs.to_epsg() != 4326:
        lau_gdf = lau_gdf.to_crs(4326)

    lau_gdf = lau_gdf.rename(
        columns={
            "GISCO_ID": "lau_code",
            "LAU_NAME": "lau_name_lau",
        }
    )[
        ["lau_code", "lau_name_lau", "geometry"]
    ].copy()
    lau_gdf["lau_code"] = lau_gdf["lau_code"].astype(str).str.strip()
    lau_gdf["lau_name_lau"] = lau_gdf["lau_name_lau"].astype(str).str.strip()
    lau_gdf["lau_code_local"] = lau_gdf["lau_code"].str.replace(
        r"^[A-Z]{2}_", "", regex=True
    )
    lau_gdf = clean_geometries(lau_gdf)

    if lau_gdf["lau_code"].duplicated().any():
        raise ValueError("France LAU codes are not unique.")

    return lau_gdf


def enrich_france_lau_with_nuts(
    france_lau: gpd.GeoDataFrame,
    nuts_path: str | Path,
) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    working = france_lau.copy()
    working["country_code"] = "FR"
    working["country_name"] = "France"
    nuts_gdf = load_nuts(nuts_path, target_countries={"FR"})
    enriched, diagnostics = enrich_lau_with_nuts(working, nuts_gdf)
    return enriched, diagnostics


def _resolve_column(columns: list[str], target: str) -> str:
    mapping = {column.lower(): column for column in columns}
    if target not in mapping:
        raise KeyError(f"Column '{target}' not found in AdminExpress layer.")
    return mapping[target]


def load_adminexpress_communes(
    adminexpress_path: str | Path,
    layer: str = "commune",
) -> gpd.GeoDataFrame:
    communes = gpd.read_file(adminexpress_path, layer=layer)
    if communes.crs is None:
        raise ValueError("AdminExpress commune layer has no CRS.")
    if communes.crs.to_epsg() != 4326:
        communes = communes.to_crs(4326)

    insee_col = _resolve_column(list(communes.columns), "insee_com")
    name_col = _resolve_column(list(communes.columns), "nom")
    dep_col = _resolve_column(list(communes.columns), "insee_dep")
    reg_col = _resolve_column(list(communes.columns), "insee_reg")
    population_col = _resolve_column(list(communes.columns), "population")
    statut_col = _resolve_column(list(communes.columns), "statut")

    communes = communes.rename(
        columns={
            insee_col: "insee_com",
            name_col: "commune_name_adminexpress",
            dep_col: "insee_dep",
            reg_col: "insee_reg",
            population_col: "adminexpress_population",
            statut_col: "adminexpress_statut",
        }
    )[
        [
            "insee_com",
            "commune_name_adminexpress",
            "insee_dep",
            "insee_reg",
            "adminexpress_population",
            "adminexpress_statut",
            "geometry",
        ]
    ].copy()
    communes["insee_com"] = communes["insee_com"].astype(str).str.strip()
    communes["commune_name_adminexpress"] = (
        communes["commune_name_adminexpress"].astype(str).str.strip()
    )
    communes = clean_geometries(communes)

    if communes["insee_com"].duplicated().any():
        raise ValueError("AdminExpress commune codes are not unique.")

    return communes


def build_france_lau_lookup(
    france_lau: gpd.GeoDataFrame,
    admin_communes: gpd.GeoDataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    lookup_cols = ["lau_code", "lau_code_local", "lau_name_lau"]
    for optional_col in ["nuts3_code", "nuts3_name"]:
        if optional_col in france_lau.columns:
            lookup_cols.append(optional_col)

    lookup = france_lau[lookup_cols].copy()
    admin_attrs = admin_communes.drop(columns=["geometry"]).copy()

    lookup = lookup.merge(
        admin_attrs,
        left_on="lau_code_local",
        right_on="insee_com",
        how="left",
        validate="1:1",
    )
    lookup["match_method"] = np.where(lookup["insee_com"].notna(), "exact_code", pd.NA)

    exact_match_count = int((lookup["match_method"] == "exact_code").sum())

    unresolved_codes = lookup["match_method"].isna()
    within_count = 0
    intersects_count = 0

    if unresolved_codes.any():
        unresolved_lau = france_lau.merge(
            lookup.loc[unresolved_codes, ["lau_code"]],
            on="lau_code",
            how="inner",
            validate="1:1",
        )
        unresolved_points = unresolved_lau[
            ["lau_code", "lau_code_local", "lau_name_lau", "geometry"]
        ].copy()
        unresolved_points["geometry"] = unresolved_points.geometry.representative_point()
        unresolved_points = gpd.GeoDataFrame(
            unresolved_points,
            geometry="geometry",
            crs=france_lau.crs,
        )

        within_join = gpd.sjoin(
            unresolved_points,
            admin_communes,
            how="left",
            predicate="within",
        ).drop(columns=["index_right"], errors="ignore")
        within_join = within_join[~within_join.index.duplicated(keep="first")]
        within_count = int(within_join["insee_com"].notna().sum())

        missing_after_within = within_join["insee_com"].isna()
        if missing_after_within.any():
            intersects_join = gpd.sjoin(
                unresolved_points.loc[missing_after_within],
                admin_communes,
                how="left",
                predicate="intersects",
            ).drop(columns=["index_right"], errors="ignore")
            intersects_join = intersects_join[
                ~intersects_join.index.duplicated(keep="first")
            ]
            intersects_count = int(intersects_join["insee_com"].notna().sum())
            for col in admin_attrs.columns:
                within_join.loc[intersects_join.index, col] = intersects_join[col]

        spatial_method = pd.Series(pd.NA, index=within_join.index, dtype="object")
        spatial_method.loc[within_join["insee_com"].notna()] = "spatial_point_within"
        if missing_after_within.any():
            intersects_mask = (
                within_join["insee_com"].notna()
                & within_join.index.isin(
                    unresolved_points.loc[missing_after_within].index
                )
            )
            spatial_method.loc[intersects_mask] = "spatial_point_intersects"

        within_join["match_method"] = spatial_method
        within_join = pd.DataFrame(within_join)
        lookup = lookup.set_index("lau_code")
        within_join = within_join.set_index("lau_code")
        for col in [
            "insee_com",
            "commune_name_adminexpress",
            "insee_dep",
            "insee_reg",
            "adminexpress_population",
            "adminexpress_statut",
            "match_method",
        ]:
            lookup.loc[within_join.index, col] = within_join[col]
        lookup = lookup.reset_index()

    lookup["match_type"] = np.where(
        lookup["match_method"].eq("exact_code"),
        "exact",
        np.where(lookup["match_method"].notna(), "fallback_spatial", pd.NA),
    )
    lookup["insee_code_changed_from_lau"] = (
        lookup["insee_com"].notna() & (lookup["insee_com"] != lookup["lau_code_local"])
    )

    for optional_col in ["nuts3_code", "nuts3_name"]:
        if optional_col not in lookup.columns:
            lookup[optional_col] = pd.NA

    lookup = lookup[FRANCE_LOOKUP_COLUMNS].copy()

    diagnostics = {
        "france_lau_total": int(len(france_lau)),
        "adminexpress_communes_total": int(len(admin_communes)),
        "exact_code_matches": exact_match_count,
        "spatial_point_within_matches": within_count,
        "spatial_point_intersects_matches": intersects_count,
        "matched_total": int(lookup["insee_com"].notna().sum()),
        "unresolved_total": int(lookup["insee_com"].isna().sum()),
        "fallback_spatial_matches": int(lookup["match_type"].eq("fallback_spatial").sum()),
        "code_changed_matches": int(lookup["insee_code_changed_from_lau"].sum()),
        "lau_missing_adminexpress_by_code_before_fallback": int(
            (~france_lau["lau_code_local"].isin(admin_communes["insee_com"])).sum()
        ),
        "adminexpress_missing_lau_by_code": int(
            (~admin_communes["insee_com"].isin(france_lau["lau_code_local"])).sum()
        ),
        "code_changed_examples": lookup.loc[
            lookup["insee_code_changed_from_lau"],
            ["lau_code_local", "insee_com", "lau_name_lau", "commune_name_adminexpress"],
        ]
        .head(20)
        .to_dict(orient="records"),
    }
    return lookup, diagnostics


def filter_france_events(events_df: pd.DataFrame) -> pd.DataFrame:
    if "lau_code" not in events_df.columns:
        raise KeyError("Input table must contain a 'lau_code' column.")

    if "country_code" in events_df.columns:
        country_mask = events_df["country_code"].astype(str).str.upper().eq("FR")
    else:
        country_mask = events_df["lau_code"].astype(str).str.startswith("FR_")

    france_events = events_df.loc[country_mask].copy()
    france_events["lau_code"] = france_events["lau_code"].astype(str).str.strip()
    france_events["lau_code_local"] = france_events["lau_code"].str.replace(
        r"^[A-Z]{2}_", "", regex=True
    )
    return france_events


def build_france_event_table(
    events_df: pd.DataFrame,
    france_lookup: pd.DataFrame,
) -> pd.DataFrame:
    france_events = filter_france_events(events_df)
    matched = france_events.merge(
        france_lookup,
        on=["lau_code", "lau_code_local"],
        how="left",
        validate="m:1",
        suffixes=("", "_lookup"),
    )

    # The Europe event table can already contain NUTS attributes. Keep those as
    # the canonical event-table columns and use the France lookup values only as
    # a fallback when the event table is missing them.
    for col in FRANCE_OUTPUT_APPEND_COLUMNS:
        lookup_col = f"{col}_lookup"
        if lookup_col not in matched.columns:
            continue
        if col in france_events.columns:
            matched[col] = matched[col].combine_first(matched[lookup_col])
            matched = matched.drop(columns=[lookup_col])
        elif col not in matched.columns:
            matched = matched.rename(columns={lookup_col: col})

    matched["insee_match_found"] = matched["insee_com"].notna()
    ordered_columns = list(events_df.columns)
    for col in FRANCE_OUTPUT_APPEND_COLUMNS + ["insee_match_found"]:
        if col not in ordered_columns:
            ordered_columns.append(col)
    matched = matched[ordered_columns].copy()
    return matched


def build_canonical_current_commune_lookup(
    france_lookup: pd.DataFrame,
) -> pd.DataFrame:
    canonical = france_lookup.copy()
    canonical["prefer_same_code"] = canonical["lau_code_local"].eq(canonical["insee_com"])
    canonical["prefer_exact_code"] = canonical["match_method"].eq("exact_code")
    canonical["prefer_same_name"] = canonical["lau_name_lau"].eq(
        canonical["commune_name_adminexpress"]
    )

    canonical = canonical.sort_values(
        by=[
            "prefer_same_code",
            "prefer_exact_code",
            "prefer_same_name",
            "lau_code",
        ],
        ascending=[False, False, False, True],
        kind="stable",
    )
    canonical = canonical.drop_duplicates(subset=["insee_com"], keep="first").copy()
    canonical = canonical.rename(
        columns={
            "insee_com": "new_insee_com",
            "commune_name_adminexpress": "new_commune_name_adminexpress",
            "lau_code": "new_lau_code",
            "lau_name_lau": "new_lau_name",
            "nuts3_code": "new_nuts3_code",
            "nuts3_name": "new_nuts3_name",
            "insee_dep": "new_insee_dep",
            "insee_reg": "new_insee_reg",
        }
    )
    return canonical[
        [
            "new_insee_com",
            "new_commune_name_adminexpress",
            "new_lau_code",
            "new_lau_name",
            "new_nuts3_code",
            "new_nuts3_name",
            "new_insee_dep",
            "new_insee_reg",
        ]
    ].copy()


def build_old_commune_to_current_mapping(
    france_lookup: pd.DataFrame,
    commune_history_path: str | Path,
    commune_movements_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    history = read_insee_csv(commune_history_path)[
        ["TYPECOM", "COM", "NCCENR", "DATE_DEBUT", "DATE_FIN"]
    ].copy()
    movements = read_insee_csv(commune_movements_path)[
        [
            "MOD",
            "DATE_EFF",
            "TYPECOM_AV",
            "COM_AV",
            "NCCENR_AV",
            "TYPECOM_AP",
            "COM_AP",
            "NCCENR_AP",
        ]
    ].copy()

    history["state_key"] = list(
        zip(
            history["TYPECOM"],
            history["COM"],
            history["NCCENR"],
            history["DATE_DEBUT"],
            history["DATE_FIN"],
        )
    )
    state_records = {
        row["state_key"]: row
        for row in history[
            ["TYPECOM", "COM", "NCCENR", "DATE_DEBUT", "DATE_FIN", "state_key"]
        ].to_dict(orient="records")
    }

    before = movements.merge(
        history[["TYPECOM", "COM", "NCCENR", "DATE_FIN", "state_key"]],
        left_on=["TYPECOM_AV", "COM_AV", "NCCENR_AV", "DATE_EFF"],
        right_on=["TYPECOM", "COM", "NCCENR", "DATE_FIN"],
        how="left",
    ).rename(columns={"state_key": "before_key"})
    after = before.merge(
        history[["TYPECOM", "COM", "NCCENR", "DATE_DEBUT", "state_key"]],
        left_on=["TYPECOM_AP", "COM_AP", "NCCENR_AP", "DATE_EFF"],
        right_on=["TYPECOM", "COM", "NCCENR", "DATE_DEBUT"],
        how="left",
        suffixes=("", "_after"),
    ).rename(columns={"state_key": "after_key"})

    adjacency: dict[tuple[str, str, str, str, str], set[tuple[str, str, str, str, str]]]
    adjacency = defaultdict(set)
    for row in after[["before_key", "after_key"]].itertuples(index=False):
        if isinstance(row.before_key, tuple) and isinstance(row.after_key, tuple):
            adjacency[row.before_key].add(row.after_key)

    active_current_states = set(
        history.loc[
            history["TYPECOM"].eq("COM") & history["DATE_FIN"].eq(""),
            "state_key",
        ]
    )
    source_states = history.loc[
        history["TYPECOM"].eq("COM") & history["DATE_FIN"].ne(""),
        "state_key",
    ].tolist()

    current_lookup = build_canonical_current_commune_lookup(france_lookup)
    mapping_rows: list[dict[str, Any]] = []
    resolution_counts = {
        "unique_current_commune": 0,
        "multiple_current_communes": 0,
        "no_current_commune_found": 0,
    }

    for source_state in source_states:
        seen = {source_state}
        queue = deque([source_state])
        terminal_states: set[tuple[str, str, str, str, str]] = set()

        while queue:
            current_state = queue.popleft()
            if current_state in active_current_states:
                terminal_states.add(current_state)
                continue

            for next_state in adjacency.get(current_state, ()):
                if next_state not in seen:
                    seen.add(next_state)
                    queue.append(next_state)

        source_record = state_records[source_state]
        match_count = len(terminal_states)
        if match_count == 0:
            resolution = "no_current_commune_found"
        elif match_count == 1:
            resolution = "unique_current_commune"
        else:
            resolution = "multiple_current_communes"
        resolution_counts[resolution] += 1

        if match_count == 0:
            mapping_rows.append(
                {
                    "old_insee_com": source_record["COM"],
                    "old_commune_name": source_record["NCCENR"],
                    "old_date_debut": source_record["DATE_DEBUT"],
                    "old_date_fin": source_record["DATE_FIN"],
                    "new_insee_com": pd.NA,
                    "new_commune_name": pd.NA,
                    "new_lau_code": pd.NA,
                    "new_lau_name": pd.NA,
                    "new_nuts3_code": pd.NA,
                    "new_nuts3_name": pd.NA,
                    "new_insee_dep": pd.NA,
                    "new_insee_reg": pd.NA,
                    "current_match_count": 0,
                    "mapping_resolution": resolution,
                    "update_ready": False,
                    "insee_code_changed": pd.NA,
                    "commune_name_changed": pd.NA,
                }
            )
            continue

        for terminal_state in sorted(terminal_states):
            terminal_record = state_records[terminal_state]
            mapping_rows.append(
                {
                    "old_insee_com": source_record["COM"],
                    "old_commune_name": source_record["NCCENR"],
                    "old_date_debut": source_record["DATE_DEBUT"],
                    "old_date_fin": source_record["DATE_FIN"],
                    "new_insee_com": terminal_record["COM"],
                    "new_commune_name": terminal_record["NCCENR"],
                    "current_match_count": match_count,
                    "mapping_resolution": resolution,
                    "update_ready": match_count == 1,
                    "insee_code_changed": source_record["COM"] != terminal_record["COM"],
                    "commune_name_changed": source_record["NCCENR"]
                    != terminal_record["NCCENR"],
                }
            )

    mapping = pd.DataFrame(mapping_rows)
    mapping = mapping.merge(
        current_lookup,
        on="new_insee_com",
        how="left",
        validate="m:1",
    )
    for base_column in [
        "new_lau_code",
        "new_lau_name",
        "new_nuts3_code",
        "new_nuts3_name",
        "new_insee_dep",
        "new_insee_reg",
    ]:
        left_column = f"{base_column}_x"
        right_column = f"{base_column}_y"
        if right_column in mapping.columns:
            if left_column in mapping.columns:
                mapping[base_column] = mapping[right_column].combine_first(
                    mapping[left_column]
                )
                mapping = mapping.drop(columns=[left_column, right_column])
            else:
                mapping = mapping.rename(columns={right_column: base_column})
    if "new_commune_name_adminexpress" in mapping.columns:
        mapping["new_commune_name"] = mapping["new_commune_name"].fillna(
            mapping["new_commune_name_adminexpress"]
        )
        mapping = mapping.drop(columns=["new_commune_name_adminexpress"])

    for column in [
        "new_lau_code",
        "new_lau_name",
        "new_nuts3_code",
        "new_nuts3_name",
        "new_insee_dep",
        "new_insee_reg",
    ]:
        if column not in mapping.columns:
            mapping[column] = pd.NA

    mapping = mapping[OLD_TO_NEW_MAPPING_COLUMNS].copy()
    mapping = mapping.sort_values(
        by=[
            "update_ready",
            "old_insee_com",
            "old_date_debut",
            "new_insee_com",
        ],
        ascending=[False, True, True, True],
        kind="stable",
    ).reset_index(drop=True)

    diagnostics = {
        "historical_commune_states_total": int(len(source_states)),
        "historical_output_rows_total": int(len(mapping)),
        "unique_current_match_states": int(
            resolution_counts["unique_current_commune"]
        ),
        "multiple_current_match_states": int(
            resolution_counts["multiple_current_communes"]
        ),
        "no_current_match_states": int(
            resolution_counts["no_current_commune_found"]
        ),
        "update_ready_rows_total": int(mapping["update_ready"].fillna(False).sum()),
        "distinct_new_communes_referenced": int(
            mapping["new_insee_com"].dropna().nunique()
        ),
        "example_unique_updates": mapping.loc[
            mapping["mapping_resolution"].eq("unique_current_commune"),
            [
                "old_insee_com",
                "old_commune_name",
                "new_insee_com",
                "new_commune_name",
                "new_nuts3_code",
            ],
        ]
        .head(20)
        .to_dict(orient="records"),
        "example_multiple_updates": mapping.loc[
            mapping["mapping_resolution"].eq("multiple_current_communes"),
            [
                "old_insee_com",
                "old_commune_name",
                "new_insee_com",
                "new_commune_name",
                "current_match_count",
            ],
        ]
        .head(20)
        .to_dict(orient="records"),
        "example_no_match_updates": mapping.loc[
            mapping["mapping_resolution"].eq("no_current_commune_found"),
            ["old_insee_com", "old_commune_name", "old_date_fin"],
        ]
        .head(20)
        .to_dict(orient="records"),
    }
    return mapping, diagnostics


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Filter the Europe LAU flood table to France and map rows to "
            "AdminExpress/INSEE communes for Gaspar comparison."
        )
    )
    parser.add_argument(
        "--tabular-file",
        required=False,
        help="Path to events_lau_long.csv or events_lau_long.parquet.",
    )
    parser.add_argument(
        "--lau",
        required=True,
        help="Path to the official Eurostat LAU GeoPackage.",
    )
    parser.add_argument(
        "--nuts",
        required=True,
        help="Path to the official Eurostat NUTS GeoPackage.",
    )
    parser.add_argument(
        "--adminexpress",
        required=True,
        help="Path to adminexpress-cog-simpl-000-2025.gpkg.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/processed/france_lau_insee_documentation",
        help=(
            "Output directory for the France event table, lookup, and diagnostics. "
            "Default: data/processed/france_lau_insee_documentation"
        ),
    )
    parser.add_argument(
        "--commune-history",
        default="data/insee_history/v_commune_depuis_1943.csv",
        help=(
            "Path to the official INSEE 'communes depuis 1943' CSV. "
            "Default: data/insee_history/v_commune_depuis_1943.csv."
        ),
    )
    parser.add_argument(
        "--commune-movements",
        default="data/insee_history/v_mvt_commune_2025.csv",
        help=(
            "Path to the official INSEE 'évènements sur les communes' CSV. "
            "Default: data/insee_history/v_mvt_commune_2025.csv."
        ),
    )
    parser.add_argument(
        "--admin-layer",
        default="commune",
        help="AdminExpress commune layer name. Default: commune.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    tabular_path = Path(args.tabular_file) if args.tabular_file else None
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading France LAU reference...")
    france_lau = load_france_lau(args.lau)
    print(f"Loaded {len(france_lau):,} France LAU polygons.")

    print("Adding NUTS mapping to France LAU...")
    france_lau, nuts_diagnostics = enrich_france_lau_with_nuts(france_lau, args.nuts)
    print("France NUTS diagnostics:", nuts_diagnostics)

    print("Loading AdminExpress communes...")
    admin_communes = load_adminexpress_communes(
        args.adminexpress,
        layer=args.admin_layer,
    )
    print(f"Loaded {len(admin_communes):,} AdminExpress communes.")

    print("Building France LAU -> INSEE lookup...")
    france_lookup, diagnostics = build_france_lau_lookup(france_lau, admin_communes)
    print("Lookup diagnostics:", json.dumps(diagnostics, indent=2, ensure_ascii=False))

    write_csv(out_dir / "fr_lau_insee_lookup.csv", france_lookup)
    docs_lookup = france_lookup[
        [
            "lau_code",
            "lau_code_local",
            "lau_name_lau",
            "insee_com",
            "commune_name_adminexpress",
            "match_type",
            "match_method",
            "nuts3_code",
            "nuts3_name",
            "insee_dep",
            "insee_reg",
            "insee_code_changed_from_lau",
        ]
    ].copy()
    write_csv(out_dir / "fr_lau_insee_lookup_documentation.csv", docs_lookup)

    print("Building historical old INSEE -> current INSEE mapping...")
    old_to_new_mapping, old_to_new_diagnostics = build_old_commune_to_current_mapping(
        france_lookup,
        args.commune_history,
        args.commune_movements,
    )
    print(
        "Historical mapping diagnostics:",
        json.dumps(old_to_new_diagnostics, indent=2, ensure_ascii=False),
    )
    write_csv(out_dir / "fr_old_insee_to_current_mapping.csv", old_to_new_mapping)
    update_ready = old_to_new_mapping.loc[
        old_to_new_mapping["update_ready"].fillna(False)
    ].copy()
    write_csv(out_dir / "fr_old_insee_to_current_update_ready.csv", update_ready)
    (out_dir / "france_old_insee_mapping_diagnostics.json").write_text(
        json.dumps(old_to_new_diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if tabular_path is not None:
        print("Reading tabularized flood table...")
        events_df = read_table(tabular_path)
        print(f"Loaded {len(events_df):,} rows.")

        print("Building France event table...")
        france_events = build_france_event_table(events_df, france_lookup)
        print(f"France event rows: {len(france_events):,}")
        write_csv(out_dir / "events_fr_insee_long.csv", france_events)

    diagnostics["nuts_diagnostics"] = nuts_diagnostics
    (out_dir / "france_insee_match_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Done.")


if __name__ == "__main__":
    main()
