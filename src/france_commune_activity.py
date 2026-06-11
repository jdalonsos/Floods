from __future__ import annotations

import calendar
import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from compare_france_jrc_gaspar_flexible import normalize_insee_code_series
from france_lau_to_insee import (
    build_canonical_current_commune_lookup,
    load_adminexpress_communes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ADMINEXPRESS_PATH = PROJECT_ROOT / "data" / "raw" / "adminexpress-cog-simpl-000-2025.gpkg"
DEFAULT_FRANCE_LOOKUP_PATH = (
    PROJECT_ROOT / "data" / "processed" / "france_lau_insee_documentation" / "fr_lau_insee_lookup.csv"
)
DEFAULT_OLD_INSEE_UPDATE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "france_lau_insee_documentation"
    / "fr_old_insee_to_current_update_ready.csv"
)
DEFAULT_JRC_EVENTS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "france_lau_insee_documentation" / "events_fr_insee_long.csv"
)
DEFAULT_GASPAR_PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "Gaspar_2015_2024.xlsx"
DEFAULT_GASPAR_FULL_HISTORY_DIR = PROJECT_ROOT / "data" / "processed" / "gaspar_all_dates"
DEFAULT_GASPAR_FULL_HISTORY_PROCESSED_PATH = (
    DEFAULT_GASPAR_FULL_HISTORY_DIR / "Gaspar_all_dates.xlsx"
)
DEFAULT_GASPAR_RAW_CSV_PATH = PROJECT_ROOT / "data" / "raw" / "catnat_gaspar.csv"
DEFAULT_GASPAR_RAW_XLSX_PATH = PROJECT_ROOT / "data" / "raw" / "catnat_gaspar.xlsx"

DEFAULT_GASPAR_SHEET = "Gaspar20152024FloodsClean"
DEFAULT_GASPAR_FULL_HISTORY_SHEET = "GasparAllDatesFloodsClean"
DEFAULT_GASPAR_FLOOD_RISK_LABELS = [
    "Inondations et/ou Coul\u00e9es de Boue",
    "Inondations Remont\u00e9e Nappe",
    "Chocs M\u00e9caniques li\u00e9s \u00e0 l'action des Vagues",
]

GASPAR_REQUIRED_COLUMNS = {
    "cod_nat_catnat",
    "cod_commune",
    "lib_commune",
    "num_risque_jo",
    "lib_risque_jo",
    "dat_deb",
    "dat_fin",
}
JRC_REQUIRED_COLUMNS = {
    "event_id",
    "start_date",
    "end_date",
    "lau_code",
    "lau_code_local",
    "insee_com",
}


@dataclass(frozen=True)
class PeriodSelection:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    label: str


def detect_csv_separator(path: str | Path) -> str:
    csv_path = Path(path)
    sample = csv_path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        return dialect.delimiter
    except csv.Error:
        return ";" if sample.count(";") > sample.count(",") else ","


def read_table(path: str | Path, *, sheet_name: str | int = 0) -> pd.DataFrame:
    table_path = Path(path)
    suffix = table_path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        separator = detect_csv_separator(table_path)
        return pd.read_csv(
            table_path,
            sep=separator,
            low_memory=False,
            dtype={"cod_commune": "string"},
            encoding="utf-8-sig",
        )
    if suffix == ".parquet":
        return pd.read_parquet(table_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(table_path, sheet_name=sheet_name, dtype={"cod_commune": "string"})
    raise ValueError(f"Unsupported tabular format: {table_path}")


def normalize_commune_name(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_risk_label(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip() or None


def join_unique_strings(series: pd.Series, *, limit: int = 5) -> str:
    values: list[str] = []
    for value in pd.Series(series).dropna().astype(str):
        clean = value.strip()
        if clean and clean not in values:
            values.append(clean)
        if len(values) >= limit:
            break
    return " | ".join(values)


def build_year_period(year: int) -> PeriodSelection:
    start = pd.Timestamp(year=year, month=1, day=1)
    end = pd.Timestamp(year=year, month=12, day=31)
    return PeriodSelection(start_date=start, end_date=end, label=f"{year}")


def build_month_period(year: int, month: int) -> PeriodSelection:
    last_day = calendar.monthrange(year, month)[1]
    start = pd.Timestamp(year=year, month=month, day=1)
    end = pd.Timestamp(year=year, month=month, day=last_day)
    return PeriodSelection(start_date=start, end_date=end, label=f"{year}-{month:02d}")


def build_single_day_period(value: object) -> PeriodSelection:
    day = pd.Timestamp(value).normalize()
    return PeriodSelection(start_date=day, end_date=day, label=day.strftime("%Y-%m-%d"))


def build_custom_range_period(start_value: object, end_value: object) -> PeriodSelection:
    start = pd.Timestamp(start_value).normalize()
    end = pd.Timestamp(end_value).normalize()
    if end < start:
        raise ValueError("End date must be on or after start date.")
    return PeriodSelection(
        start_date=start,
        end_date=end,
        label=f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
    )


def filter_records_active_between(
    df: pd.DataFrame,
    *,
    start_col: str,
    end_col: str,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> pd.DataFrame:
    mask = (
        df[start_col].notna()
        & df[end_col].notna()
        & df[start_col].le(period_end)
        & df[end_col].ge(period_start)
    )
    return df.loc[mask].copy()


def load_france_lookup(path: str | Path = DEFAULT_FRANCE_LOOKUP_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False, dtype="string")
    df["insee_com"] = normalize_insee_code_series(df["insee_com"])
    df["lau_code_local"] = normalize_insee_code_series(df["lau_code_local"])
    df["lau_code"] = df["lau_code"].astype("string").str.strip()
    return df


def build_current_commune_reference(france_lookup: pd.DataFrame) -> pd.DataFrame:
    canonical = build_canonical_current_commune_lookup(france_lookup)
    canonical = canonical.rename(
        columns={
            "new_insee_com": "insee_com",
            "new_commune_name_adminexpress": "commune_name_current",
            "new_lau_code": "lau_code",
            "new_lau_name": "lau_name_lau",
            "new_nuts3_code": "nuts3_code",
            "new_nuts3_name": "nuts3_name",
            "new_insee_dep": "insee_dep",
            "new_insee_reg": "insee_reg",
        }
    )

    extras = (
        france_lookup[
            [
                "insee_com",
                "adminexpress_population",
                "adminexpress_statut",
                "match_method",
                "match_type",
                "insee_code_changed_from_lau",
            ]
        ]
        .drop_duplicates(subset=["insee_com"])
        .copy()
    )

    current = canonical.merge(extras, on="insee_com", how="left", validate="1:1")
    current["insee_com"] = normalize_insee_code_series(current["insee_com"])
    current["lau_code_local"] = current["lau_code"].astype("string").str.replace(
        r"^[A-Z]{2}_",
        "",
        regex=True,
    )
    return current


def load_historical_insee_updates(
    path: str | Path = DEFAULT_OLD_INSEE_UPDATE_PATH,
) -> pd.DataFrame:
    history = pd.read_csv(path, low_memory=False, dtype="string")
    if "update_ready" in history.columns:
        history = history[history["update_ready"].astype("string").str.lower().eq("true")].copy()

    history["old_insee_com"] = normalize_insee_code_series(history["old_insee_com"])
    history["new_insee_com"] = normalize_insee_code_series(history["new_insee_com"])
    history = history.dropna(subset=["old_insee_com", "new_insee_com"]).copy()
    history = history.sort_values(
        by=["old_insee_com", "old_date_fin", "new_insee_com"],
        ascending=[True, True, True],
        kind="stable",
    )
    history = history.drop_duplicates(subset=["old_insee_com"], keep="last").copy()
    return history


def build_unique_name_reference(
    current_lookup: pd.DataFrame,
    *,
    name_column: str,
    method_name: str,
) -> pd.DataFrame:
    name_reference = current_lookup[["insee_com", name_column]].dropna().copy()
    name_reference["name_key"] = name_reference[name_column].map(normalize_commune_name)
    name_reference = name_reference.dropna(subset=["name_key"]).copy()

    unique_keys = (
        name_reference.groupby("name_key", dropna=False)["insee_com"].nunique().rename("n")
    )
    unique_keys = unique_keys[unique_keys.eq(1)].index

    unique_reference = name_reference[name_reference["name_key"].isin(unique_keys)].copy()
    unique_reference = unique_reference.drop_duplicates(subset=["name_key"], keep="first")
    unique_reference["gaspar_commune_match_method"] = method_name
    return unique_reference[["name_key", "insee_com", "gaspar_commune_match_method"]].copy()


def prepare_processed_gaspar_rows(
    path: str | Path = DEFAULT_GASPAR_PROCESSED_PATH,
    *,
    sheet_name: str | int = DEFAULT_GASPAR_SHEET,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = read_table(path, sheet_name=sheet_name)
    missing = GASPAR_REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise KeyError(f"Gaspar input is missing required columns: {sorted(missing)}")

    df = raw.copy()
    df["gaspar_start_date"] = pd.to_datetime(df["dat_deb"], errors="coerce").dt.normalize()
    df["gaspar_end_date"] = pd.to_datetime(df["dat_fin"], errors="coerce").dt.normalize()
    df["activity_start_date"] = df["gaspar_start_date"]
    df["activity_end_date"] = df["gaspar_end_date"]
    df["cod_nat_catnat"] = df["cod_nat_catnat"].astype("string").str.strip()
    df["gaspar_commune_name"] = df["lib_commune"].astype("string").str.strip()
    df["gaspar_source_cod_commune"] = df["cod_commune"].astype("string").str.strip()
    df["gaspar_source_insee_com"] = normalize_insee_code_series(df["cod_commune"])
    invalid_mask = (
        df["cod_nat_catnat"].isna()
        | df["gaspar_start_date"].isna()
        | df["gaspar_end_date"].isna()
    )
    df = df.loc[~invalid_mask].copy()

    df["gaspar_event_uid"] = (
        df["cod_nat_catnat"]
        + "__"
        + df["gaspar_start_date"].dt.strftime("%Y%m%d")
        + "__"
        + df["gaspar_end_date"].dt.strftime("%Y%m%d")
    )

    diagnostics = {
        "source_kind": "processed_workbook",
        "raw_rows": int(len(raw)),
        "rows_after_date_parsing": int(len(df)),
        "rows_dropped_missing_core_fields": int(invalid_mask.sum()),
    }
    return df.reset_index(drop=True), diagnostics


def prepare_raw_gaspar_rows(
    path: str | Path,
    *,
    flood_risk_labels: list[str] | None = None,
    start_date_lower_bound: str | pd.Timestamp | None = None,
    end_date_upper_bound: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = read_table(path)
    missing = GASPAR_REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise KeyError(f"Gaspar raw input is missing required columns: {sorted(missing)}")

    labels = flood_risk_labels or DEFAULT_GASPAR_FLOOD_RISK_LABELS
    normalized_labels = {
        normalized
        for normalized in (normalize_risk_label(label) for label in labels)
        if normalized
    }
    df = raw.copy()
    df["gaspar_start_date"] = pd.to_datetime(df["dat_deb"], errors="coerce").dt.normalize()
    df["gaspar_end_date"] = pd.to_datetime(df["dat_fin"], errors="coerce").dt.normalize()
    df["activity_start_date"] = df["gaspar_start_date"]
    df["activity_end_date"] = df["gaspar_end_date"]
    df["cod_nat_catnat"] = df["cod_nat_catnat"].astype("string").str.strip()
    df["gaspar_commune_name"] = df["lib_commune"].astype("string").str.strip()
    df["gaspar_source_cod_commune"] = df["cod_commune"].astype("string").str.strip()
    df["gaspar_source_insee_com"] = normalize_insee_code_series(df["cod_commune"])
    df["gaspar_risk_label_normalized"] = df["lib_risque_jo"].map(normalize_risk_label)

    risk_mask = df["gaspar_risk_label_normalized"].isin(normalized_labels)
    filtered = df.loc[risk_mask].copy()

    date_window_mask = pd.Series(True, index=filtered.index)
    lower_bound = pd.to_datetime(start_date_lower_bound, errors="coerce") if start_date_lower_bound else pd.NaT
    upper_bound = pd.to_datetime(end_date_upper_bound, errors="coerce") if end_date_upper_bound else pd.NaT
    if start_date_lower_bound is not None and pd.isna(lower_bound):
        raise ValueError(f"Could not parse start_date_lower_bound value: {start_date_lower_bound}")
    if end_date_upper_bound is not None and pd.isna(upper_bound):
        raise ValueError(f"Could not parse end_date_upper_bound value: {end_date_upper_bound}")
    if pd.notna(lower_bound):
        date_window_mask &= filtered["gaspar_start_date"].ge(lower_bound)
    if pd.notna(upper_bound):
        date_window_mask &= filtered["gaspar_end_date"].le(upper_bound)
    filtered = filtered.loc[date_window_mask].copy()

    invalid_mask = (
        filtered["cod_nat_catnat"].isna()
        | filtered["gaspar_start_date"].isna()
        | filtered["gaspar_end_date"].isna()
    )
    filtered = filtered.loc[~invalid_mask].copy()

    keep_cols = [
        "cod_nat_catnat",
        "cod_commune",
        "lib_commune",
        "num_risque_jo",
        "lib_risque_jo",
        "dat_deb",
        "dat_fin",
        "gaspar_start_date",
        "gaspar_end_date",
        "gaspar_commune_name",
        "gaspar_source_cod_commune",
        "gaspar_source_insee_com",
    ]
    filtered = filtered[keep_cols].drop_duplicates().reset_index(drop=True)

    filtered["gaspar_event_uid"] = (
        filtered["cod_nat_catnat"]
        + "__"
        + filtered["gaspar_start_date"].dt.strftime("%Y%m%d")
        + "__"
        + filtered["gaspar_end_date"].dt.strftime("%Y%m%d")
    )

    diagnostics = {
        "source_kind": "raw_live_transform",
        "raw_rows": int(len(raw)),
        "rows_after_flood_risk_filter": int(risk_mask.sum()),
        "optional_date_window_applied": bool(pd.notna(lower_bound) or pd.notna(upper_bound)),
        "rows_after_optional_date_window": int(date_window_mask.sum()),
        "rows_dropped_missing_core_fields": int(invalid_mask.sum()),
        "canonical_rows_after_dedup": int(len(filtered)),
        "unique_decrees": int(filtered["cod_nat_catnat"].nunique()),
        "unique_event_uids": int(filtered["gaspar_event_uid"].nunique()),
    }
    return filtered, diagnostics


def resolve_gaspar_current_communes(
    gaspar_df: pd.DataFrame,
    *,
    france_lookup: pd.DataFrame,
    historical_updates: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    current_lookup = build_current_commune_reference(france_lookup)
    history_lookup = historical_updates[["old_insee_com", "new_insee_com"]].copy()

    admin_name_lookup = build_unique_name_reference(
        current_lookup,
        name_column="commune_name_current",
        method_name="current_name_unique_adminexpress",
    )
    lau_name_lookup = build_unique_name_reference(
        current_lookup,
        name_column="lau_name_lau",
        method_name="current_name_unique_lau",
    )

    resolved = gaspar_df.copy()
    resolved["gaspar_name_key"] = resolved["gaspar_commune_name"].map(normalize_commune_name)
    resolved["insee_com"] = pd.Series(pd.NA, index=resolved.index, dtype="string")
    resolved["gaspar_commune_match_method"] = pd.Series(pd.NA, index=resolved.index, dtype="string")

    exact_mask = resolved["gaspar_source_insee_com"].isin(current_lookup["insee_com"])
    resolved.loc[exact_mask, "insee_com"] = resolved.loc[exact_mask, "gaspar_source_insee_com"]
    resolved.loc[exact_mask, "gaspar_commune_match_method"] = "current_code_exact"

    unresolved_code_mask = resolved["insee_com"].isna() & resolved["gaspar_source_insee_com"].notna()
    if unresolved_code_mask.any():
        mapped_history = resolved.loc[unresolved_code_mask, ["gaspar_source_insee_com"]].merge(
            history_lookup,
            left_on="gaspar_source_insee_com",
            right_on="old_insee_com",
            how="left",
            validate="m:1",
        )
        mapped_history = mapped_history["new_insee_com"]
        history_index = resolved.loc[unresolved_code_mask].index
        history_series = pd.Series(mapped_history.to_numpy(), index=history_index, dtype="string")
        history_hit_mask = history_series.notna()
        hit_index = history_series.index[history_hit_mask]
        resolved.loc[hit_index, "insee_com"] = history_series.loc[hit_index]
        resolved.loc[hit_index, "gaspar_commune_match_method"] = "historical_code_update_ready"

    unresolved_name_mask = resolved["insee_com"].isna() & resolved["gaspar_name_key"].notna()
    if unresolved_name_mask.any():
        name_matches = resolved.loc[unresolved_name_mask, ["gaspar_name_key"]].merge(
            admin_name_lookup,
            left_on="gaspar_name_key",
            right_on="name_key",
            how="left",
            validate="m:1",
        )
        name_matches = name_matches[["insee_com", "gaspar_commune_match_method"]]
        name_index = resolved.loc[unresolved_name_mask].index
        admin_name_series = pd.Series(name_matches["insee_com"].to_numpy(), index=name_index, dtype="string")
        admin_method_series = pd.Series(
            name_matches["gaspar_commune_match_method"].to_numpy(),
            index=name_index,
            dtype="string",
        )
        admin_hit_mask = admin_name_series.notna()
        admin_hit_index = admin_name_series.index[admin_hit_mask]
        resolved.loc[admin_hit_index, "insee_com"] = admin_name_series.loc[admin_hit_index]
        resolved.loc[admin_hit_index, "gaspar_commune_match_method"] = admin_method_series.loc[
            admin_hit_index
        ]

    unresolved_lau_name_mask = resolved["insee_com"].isna() & resolved["gaspar_name_key"].notna()
    if unresolved_lau_name_mask.any():
        lau_matches = resolved.loc[unresolved_lau_name_mask, ["gaspar_name_key"]].merge(
            lau_name_lookup,
            left_on="gaspar_name_key",
            right_on="name_key",
            how="left",
            validate="m:1",
        )
        lau_matches = lau_matches[["insee_com", "gaspar_commune_match_method"]]
        lau_index = resolved.loc[unresolved_lau_name_mask].index
        lau_name_series = pd.Series(lau_matches["insee_com"].to_numpy(), index=lau_index, dtype="string")
        lau_method_series = pd.Series(
            lau_matches["gaspar_commune_match_method"].to_numpy(),
            index=lau_index,
            dtype="string",
        )
        lau_hit_mask = lau_name_series.notna()
        lau_hit_index = lau_name_series.index[lau_hit_mask]
        resolved.loc[lau_hit_index, "insee_com"] = lau_name_series.loc[lau_hit_index]
        resolved.loc[lau_hit_index, "gaspar_commune_match_method"] = lau_method_series.loc[
            lau_hit_index
        ]

    resolved = resolved.merge(
        current_lookup.add_prefix("current_"),
        left_on="insee_com",
        right_on="current_insee_com",
        how="left",
        validate="m:1",
    )
    resolved["gaspar_commune_match_found"] = resolved["insee_com"].notna()
    resolved["gaspar_commune_code_changed"] = (
        resolved["gaspar_commune_match_found"]
        & resolved["gaspar_source_insee_com"].notna()
        & resolved["gaspar_source_insee_com"].ne(resolved["insee_com"])
    )
    resolved["commune_name_current"] = resolved["current_commune_name_current"]
    resolved["lau_code"] = resolved["current_lau_code"]
    resolved["lau_code_local"] = resolved["current_lau_code_local"]
    resolved["lau_name_lau"] = resolved["current_lau_name_lau"]
    resolved["nuts3_code"] = resolved["current_nuts3_code"]
    resolved["nuts3_name"] = resolved["current_nuts3_name"]
    resolved["insee_dep"] = resolved["current_insee_dep"]
    resolved["insee_reg"] = resolved["current_insee_reg"]

    diagnostics = {
        "resolved_rows": int(resolved["gaspar_commune_match_found"].sum()),
        "unresolved_rows": int((~resolved["gaspar_commune_match_found"]).sum()),
        "match_method_counts": {
            str(key): int(value)
            for key, value in resolved["gaspar_commune_match_method"].fillna("unresolved").value_counts().items()
        },
        "code_changed_rows": int(resolved["gaspar_commune_code_changed"].sum()),
        "unresolved_examples": resolved.loc[
            ~resolved["gaspar_commune_match_found"],
            ["gaspar_source_cod_commune", "gaspar_commune_name", "cod_nat_catnat"],
        ]
        .head(20)
        .to_dict(orient="records"),
    }
    return resolved, diagnostics


def prepare_jrc_activity_rows(
    path: str | Path = DEFAULT_JRC_EVENTS_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = read_table(path)
    missing = JRC_REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise KeyError(f"JRC input is missing required columns: {sorted(missing)}")

    df = raw.copy()
    if "insee_match_found" in df.columns:
        df = df[df["insee_match_found"].fillna(False)].copy()

    df["insee_com"] = normalize_insee_code_series(df["insee_com"])
    df["jrc_event_id"] = df["event_id"].astype("string").str.strip()
    df["jrc_start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.normalize()
    df["jrc_end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.normalize()
    df["activity_start_date"] = df["jrc_start_date"]
    df["activity_end_date"] = df["jrc_end_date"]
    df["lau_code"] = df["lau_code"].astype("string").str.strip()
    df["lau_code_local"] = normalize_insee_code_series(df["lau_code_local"])
    df["commune_name_current"] = (
        df.get("commune_name_adminexpress", df.get("lau_name", pd.Series(pd.NA, index=df.index)))
        .astype("string")
        .str.strip()
    )

    invalid_mask = (
        df["jrc_event_id"].isna()
        | df["insee_com"].isna()
        | df["jrc_start_date"].isna()
        | df["jrc_end_date"].isna()
    )
    df = df.loc[~invalid_mask].copy()

    key_cols = ["jrc_event_id", "insee_com", "jrc_start_date", "jrc_end_date"]
    duplicate_rows = int(df.duplicated(subset=key_cols).sum())
    df = (
        df.sort_values(key_cols, kind="stable")
        .drop_duplicates(subset=key_cols)
        .reset_index(drop=True)
    )

    keep_cols = [
        "jrc_event_id",
        "event_id",
        "activity_start_date",
        "activity_end_date",
        "jrc_start_date",
        "jrc_end_date",
        "insee_com",
        "commune_name_current",
        "lau_code",
        "lau_code_local",
        "lau_name",
        "nuts3_code",
        "nuts3_name",
        "max_depth_cm",
        "flooded_pixels",
        "flooded_area_m2",
        "gfm_extent_km2",
        "enhanced_extent_km2",
        "source_year_folder",
        "raster_file",
    ]
    keep_cols = [column for column in keep_cols if column in df.columns]
    df = df[keep_cols].copy()

    diagnostics = {
        "canonical_rows": int(len(df)),
        "duplicate_rows_dropped": duplicate_rows,
        "unique_events": int(df["jrc_event_id"].nunique()),
        "unique_communes": int(df["insee_com"].nunique()),
    }
    return df, diagnostics


def load_commune_geometries(
    adminexpress_path: str | Path = DEFAULT_ADMINEXPRESS_PATH,
    *,
    simplify_tolerance: float = 0.0,
) -> gpd.GeoDataFrame:
    communes = load_adminexpress_communes(adminexpress_path)
    keep_cols = [
        "insee_com",
        "commune_name_adminexpress",
        "insee_dep",
        "insee_reg",
        "adminexpress_population",
        "adminexpress_statut",
        "geometry",
    ]
    communes = communes[keep_cols].copy()
    if simplify_tolerance > 0:
        communes["geometry"] = communes.geometry.simplify(
            simplify_tolerance,
            preserve_topology=True,
        )
    communes = communes.rename(columns={"commune_name_adminexpress": "commune_name_current"})
    return communes


def build_department_boundaries(
    communes: gpd.GeoDataFrame,
    *,
    simplify_tolerance: float = 0.01,
) -> gpd.GeoDataFrame:
    department_cols = ["insee_dep", "insee_reg", "geometry"]
    departments = communes[department_cols].dissolve(by="insee_dep", as_index=False)
    if simplify_tolerance > 0:
        departments["geometry"] = departments.geometry.simplify(
            simplify_tolerance,
            preserve_topology=True,
        )
    return departments


def build_france_outline(
    communes: gpd.GeoDataFrame,
    *,
    simplify_tolerance: float = 0.02,
) -> gpd.GeoDataFrame:
    outline_geometry = communes.geometry.union_all()
    outline = gpd.GeoDataFrame(
        {"label": ["France"], "geometry": [outline_geometry]},
        geometry="geometry",
        crs=communes.crs,
    )
    if simplify_tolerance > 0:
        outline["geometry"] = outline.geometry.simplify(
            simplify_tolerance,
            preserve_topology=True,
        )
    return outline


def aggregate_gaspar_activity(active_rows: pd.DataFrame) -> pd.DataFrame:
    if active_rows.empty:
        return pd.DataFrame(
            columns=[
                "insee_com",
                "commune_name_current",
                "insee_dep",
                "insee_reg",
                "lau_code",
                "lau_code_local",
                "lau_name_lau",
                "gaspar_row_count",
                "gaspar_unique_event_count",
                "gaspar_unique_decree_count",
                "gaspar_risk_labels",
                "gaspar_match_methods",
            ]
        )

    grouped = (
        active_rows.groupby("insee_com", dropna=False)
        .agg(
            commune_name_current=("commune_name_current", "first"),
            insee_dep=("insee_dep", "first"),
            insee_reg=("insee_reg", "first"),
            lau_code=("lau_code", "first"),
            lau_code_local=("lau_code_local", "first"),
            lau_name_lau=("lau_name_lau", "first"),
            gaspar_row_count=("gaspar_event_uid", "size"),
            gaspar_unique_event_count=("gaspar_event_uid", "nunique"),
            gaspar_unique_decree_count=("cod_nat_catnat", "nunique"),
            gaspar_risk_labels=("lib_risque_jo", join_unique_strings),
            gaspar_match_methods=("gaspar_commune_match_method", join_unique_strings),
        )
        .reset_index()
    )
    return grouped


def aggregate_jrc_activity(active_rows: pd.DataFrame) -> pd.DataFrame:
    if active_rows.empty:
        return pd.DataFrame(
            columns=[
                "insee_com",
                "commune_name_current",
                "nuts3_code",
                "nuts3_name",
                "lau_code",
                "lau_code_local",
                "lau_name",
                "jrc_row_count",
                "jrc_unique_event_count",
                "jrc_max_depth_cm",
                "jrc_total_flooded_area_m2",
            ]
        )

    grouped = (
        active_rows.groupby("insee_com", dropna=False)
        .agg(
            commune_name_current=("commune_name_current", "first"),
            nuts3_code=("nuts3_code", "first"),
            nuts3_name=("nuts3_name", "first"),
            lau_code=("lau_code", "first"),
            lau_code_local=("lau_code_local", "first"),
            lau_name=("lau_name", "first"),
            jrc_row_count=("jrc_event_id", "size"),
            jrc_unique_event_count=("jrc_event_id", "nunique"),
            jrc_max_depth_cm=("max_depth_cm", "max"),
            jrc_total_flooded_area_m2=("flooded_area_m2", "sum"),
        )
        .reset_index()
    )
    return grouped


def build_comparison_activity(
    gaspar_active: pd.DataFrame,
    jrc_active: pd.DataFrame,
) -> pd.DataFrame:
    gaspar_agg = aggregate_gaspar_activity(gaspar_active)
    jrc_agg = aggregate_jrc_activity(jrc_active)

    merged = gaspar_agg.merge(
        jrc_agg,
        on="insee_com",
        how="outer",
        suffixes=("_gaspar", "_jrc"),
    )
    merged["commune_name_current"] = merged["commune_name_current_gaspar"].combine_first(
        merged["commune_name_current_jrc"]
    )
    merged["lau_code"] = merged["lau_code_gaspar"].combine_first(merged["lau_code_jrc"])
    merged["lau_code_local"] = merged["lau_code_local_gaspar"].combine_first(
        merged["lau_code_local_jrc"]
    )
    merged["insee_dep"] = merged["insee_dep"].astype("string")
    merged["insee_reg"] = merged["insee_reg"].astype("string")

    for column in [
        "gaspar_row_count",
        "gaspar_unique_event_count",
        "gaspar_unique_decree_count",
        "jrc_row_count",
        "jrc_unique_event_count",
        "jrc_total_flooded_area_m2",
    ]:
        if column in merged.columns:
            merged[column] = merged[column].fillna(0)

    merged["comparison_class"] = "inactive"
    gaspar_mask = merged["gaspar_row_count"].fillna(0).gt(0)
    jrc_mask = merged["jrc_row_count"].fillna(0).gt(0)
    merged.loc[gaspar_mask & ~jrc_mask, "comparison_class"] = "gaspar_only"
    merged.loc[~gaspar_mask & jrc_mask, "comparison_class"] = "jrc_only"
    merged.loc[gaspar_mask & jrc_mask, "comparison_class"] = "both"

    keep_cols = [
        "insee_com",
        "commune_name_current",
        "insee_dep",
        "insee_reg",
        "lau_code",
        "lau_code_local",
        "gaspar_row_count",
        "gaspar_unique_event_count",
        "gaspar_unique_decree_count",
        "gaspar_risk_labels",
        "gaspar_match_methods",
        "jrc_row_count",
        "jrc_unique_event_count",
        "jrc_max_depth_cm",
        "jrc_total_flooded_area_m2",
        "comparison_class",
    ]
    keep_cols = [column for column in keep_cols if column in merged.columns]
    return merged[keep_cols].copy()
