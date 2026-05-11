"""
Flexible France JRC vs Gaspar comparison with broader date rules and
department-level rollups.

This script is self-contained and keeps the earlier commune-level comparison
logic as the strict baseline, while adding:

- a default 30-day date window
- an additional cross-date condition based on comparing one source's start
  date to the other source's end date, in both directions
- department-level / NUTS3-adjacent canonical outputs and match tables

The main commune-level match rule becomes:

- same normalized INSEE commune code
- and at least one of:
  - abs(JRC start - Gaspar start) <= window AND
    abs(JRC end - Gaspar end) <= window
  - abs(JRC start - Gaspar end) <= window AND
    abs(Gaspar start - JRC end) <= window
  - the two intervals overlap after expanding each side by the same window
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

EXCEL_ROW_LIMIT = 1_000_000
JRC_REQUIRED_COLUMNS = {
    "event_id",
    "start_date",
    "end_date",
    "insee_com",
}
GASPAR_REQUIRED_COLUMNS = {
    "cod_nat_catnat",
    "cod_commune",
    "lib_commune",
    "dat_deb",
    "dat_fin",
}


def write_markdown(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_single_sheet_excel(path: Path, sheet_name: str, df: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def relocate_existing_detail_files(
    out_dir: Path,
    details_dir: Path,
    file_names: list[str],
) -> None:
    details_dir.mkdir(parents=True, exist_ok=True)
    for file_name in file_names:
        legacy_path = out_dir / file_name
        target_path = details_dir / file_name
        if not legacy_path.exists() or legacy_path == target_path:
            continue
        if target_path.exists():
            target_path.unlink()
        legacy_path.replace(target_path)


def build_coverage_overview(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def build_best_match_overview(
    best_matches: pd.DataFrame,
    ranked_scores: pd.DataFrame,
    matched_col: str,
    exact_col: str,
) -> pd.DataFrame:
    if best_matches.empty:
        return pd.DataFrame(
            columns=[
                "jrc_event_id",
                "gaspar_event_uid",
                "cod_nat_catnat",
                "jrc_start_date",
                "jrc_end_date",
                "gaspar_start_date",
                "gaspar_end_date",
                matched_col,
                exact_col,
                "jrc_match_share",
                "gaspar_match_share",
                "min_total_abs_date_diff_days",
                "mean_total_abs_date_diff_days",
                "max_interval_overlap_days",
                "reciprocal_best_match",
            ]
        )

    reciprocal = pd.DataFrame(
        columns=["jrc_event_id", "gaspar_event_uid", "reciprocal_best_match"]
    )
    if not ranked_scores.empty and "reciprocal_best_match" in ranked_scores.columns:
        reciprocal = ranked_scores[
            ["jrc_event_id", "gaspar_event_uid", "reciprocal_best_match"]
        ].drop_duplicates()

    overview = best_matches.merge(
        reciprocal,
        on=["jrc_event_id", "gaspar_event_uid"],
        how="left",
        validate="1:1",
    )
    overview["reciprocal_best_match"] = overview["reciprocal_best_match"].fillna(False)

    keep_cols = [
        "jrc_event_id",
        "gaspar_event_uid",
        "cod_nat_catnat",
        "jrc_start_date",
        "jrc_end_date",
        "gaspar_start_date",
        "gaspar_end_date",
        matched_col,
        exact_col,
        "jrc_match_share",
        "gaspar_match_share",
        "min_total_abs_date_diff_days",
        "mean_total_abs_date_diff_days",
        "max_interval_overlap_days",
        "reciprocal_best_match",
    ]
    keep_cols = [col for col in keep_cols if col in overview.columns]
    return overview[keep_cols].copy()


def build_output_guide_markdown(
    *,
    title: str,
    window_days: int,
    top_level_files: list[str],
    details_dir_name: str,
    coverage_overview: pd.DataFrame,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"This comparison used a date window of **{window_days} days**.",
        "",
        "## Open These First",
        "",
    ]
    for file_name in top_level_files:
        lines.append(f"- `{file_name}`")

    lines.extend(
        [
            "",
            "## How To Read The Numbers",
            "",
            "- `unique events` means unique `jrc_event_id` or unique `gaspar_event_uid`.",
            "- `canonical rows` means one comparison row at the chosen level.",
            "- for commune level, one canonical row is one commune-event row.",
            "- for department level, one canonical row is one department-event row.",
            "- unmatched row tables can be much larger than unmatched unique event counts because one event can be unmatched in many communes or departments.",
            "",
            "## Detailed Audit Tables",
            "",
            f"- all detailed raw match tables, canonical tables, unmatched tables, parquet files, and diagnostics are stored in `{details_dir_name}/`.",
            "",
            "## Coverage Overview",
            "",
        ]
    )

    if coverage_overview.empty:
        lines.append("No coverage overview rows available.")
    else:
        for _, row in coverage_overview.iterrows():
            lines.append(
                f"- {row['level']} / {row['measurement']}: "
                f"JRC matched {row['jrc_matched']} of {row['jrc_total']}, "
                f"Gaspar matched {row['gaspar_matched']} of {row['gaspar_total']}."
            )

    lines.extend(
        [
            "",
            "## Quick Reading Path",
            "",
            "1. Start with `comparison_summary.csv` for the headline counts.",
            "2. Open `coverage_overview.csv` to distinguish unique event counts from row counts.",
            "3. Open the best-match overview table(s) to review the strongest suggested event pairings.",
            "4. Use the workbook and the detailed tables only when you need deeper audit or debugging.",
        ]
    )
    return "\n".join(lines) + "\n"


def normalize_insee_code_series(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.upper()
    normalized = normalized.replace(
        {
            "": pd.NA,
            "NAN": pd.NA,
            "NONE": pd.NA,
            "<NA>": pd.NA,
        }
    )
    normalized = normalized.str.replace(r"\.0$", "", regex=True)
    numeric_mask = normalized.str.fullmatch(r"\d+").fillna(False)
    normalized.loc[numeric_mask] = normalized.loc[numeric_mask].str.zfill(5)
    return normalized


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


def maybe_write_parquet(path: Path, df: pd.DataFrame) -> str | None:
    try:
        df.to_parquet(path, index=False)
        return str(path)
    except Exception:
        return None


def write_excel_workbook(
    path: Path,
    tables: list[tuple[str, pd.DataFrame]],
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


def prepare_jrc_commune_events(jrc_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = read_table(jrc_path)
    missing = JRC_REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise KeyError(f"JRC input is missing required columns: {sorted(missing)}")

    df = raw.copy()
    if "insee_match_found" in df.columns:
        df = df[df["insee_match_found"].fillna(False)].copy()

    df["insee_com"] = normalize_insee_code_series(df["insee_com"])
    df["jrc_start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.normalize()
    df["jrc_end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.normalize()
    df["jrc_event_id"] = df["event_id"].astype(str).str.strip()
    df["jrc_commune_name"] = (
        df.get(
            "commune_name_adminexpress",
            df.get("lau_name", pd.Series(pd.NA, index=df.index)),
        )
        .astype("string")
        .str.strip()
    )

    invalid_mask = (
        df["insee_com"].isna()
        | df["jrc_start_date"].isna()
        | df["jrc_end_date"].isna()
        | df["jrc_event_id"].eq("")
    )
    invalid_rows = int(invalid_mask.sum())
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
        "raster_file",
        "source_year_folder",
        "jrc_start_date",
        "jrc_end_date",
        "duration_days",
        "flood_id",
        "gfm_extent_km2",
        "enhanced_extent_km2",
        "insee_com",
        "jrc_commune_name",
        "nuts3_code",
        "nuts3_name",
        "max_depth_cm",
        "flooded_pixels",
        "flooded_area_m2",
    ]
    keep_cols = [col for col in keep_cols if col in df.columns]
    df = df[keep_cols].copy()

    event_stats = (
        df.groupby("jrc_event_id", dropna=False)
        .agg(
            jrc_event_start_date=("jrc_start_date", "first"),
            jrc_event_end_date=("jrc_end_date", "first"),
            jrc_total_communes=("insee_com", "nunique"),
            jrc_total_nuts3=("nuts3_code", "nunique"),
        )
        .reset_index()
    )

    diagnostics = {
        "raw_rows": int(len(raw)),
        "rows_after_insee_match_filter": int(len(df) + invalid_rows + duplicate_rows),
        "invalid_rows_dropped": invalid_rows,
        "duplicate_event_commune_rows_dropped": duplicate_rows,
        "canonical_rows": int(len(df)),
        "unique_jrc_events": int(df["jrc_event_id"].nunique()),
        "unique_jrc_communes": int(df["insee_com"].nunique()),
    }
    return df, {"diagnostics": diagnostics, "event_stats": event_stats}


def prepare_gaspar_commune_events(
    gaspar_path: str | Path,
    sheet_name: str | int = 0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_excel(gaspar_path, sheet_name=sheet_name, dtype={"cod_commune": "string"})
    missing = GASPAR_REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise KeyError(f"Gaspar input is missing required columns: {sorted(missing)}")

    df = raw.copy()
    df["insee_com"] = normalize_insee_code_series(df["cod_commune"])
    df["gaspar_start_date"] = pd.to_datetime(df["dat_deb"], errors="coerce").dt.normalize()
    df["gaspar_end_date"] = pd.to_datetime(df["dat_fin"], errors="coerce").dt.normalize()
    df["cod_nat_catnat"] = df["cod_nat_catnat"].astype("string").str.strip()
    df["gaspar_commune_name"] = df["lib_commune"].astype("string").str.strip()

    invalid_mask = (
        df["cod_nat_catnat"].isna()
        | df["insee_com"].isna()
        | df["gaspar_start_date"].isna()
        | df["gaspar_end_date"].isna()
    )
    invalid_rows = int(invalid_mask.sum())
    df = df.loc[~invalid_mask].copy()

    df["gaspar_event_uid"] = (
        df["cod_nat_catnat"]
        + "__"
        + df["gaspar_start_date"].dt.strftime("%Y%m%d")
        + "__"
        + df["gaspar_end_date"].dt.strftime("%Y%m%d")
    )

    key_cols = ["gaspar_event_uid", "insee_com", "gaspar_start_date", "gaspar_end_date"]
    duplicate_rows = int(df.duplicated(subset=key_cols).sum())
    df = (
        df.sort_values(key_cols, kind="stable")
        .drop_duplicates(subset=key_cols)
        .reset_index(drop=True)
    )

    keep_cols = [
        "gaspar_event_uid",
        "cod_nat_catnat",
        "insee_com",
        "gaspar_commune_name",
        "num_risque_jo",
        "lib_risque_jo",
        "gaspar_start_date",
        "gaspar_end_date",
    ]
    keep_cols = [col for col in keep_cols if col in df.columns]
    df = df[keep_cols].copy()

    date_pair_counts = (
        raw.assign(
            dat_deb=pd.to_datetime(raw["dat_deb"], errors="coerce").dt.normalize(),
            dat_fin=pd.to_datetime(raw["dat_fin"], errors="coerce").dt.normalize(),
        )
        .dropna(subset=["cod_nat_catnat", "dat_deb", "dat_fin"])
        .groupby("cod_nat_catnat", dropna=False)[["dat_deb", "dat_fin"]]
        .apply(lambda g: g.drop_duplicates().shape[0])
        .rename("unique_date_pairs")
        .reset_index()
    )

    event_stats = (
        df.groupby("gaspar_event_uid", dropna=False)
        .agg(
            cod_nat_catnat=("cod_nat_catnat", "first"),
            gaspar_event_start_date=("gaspar_start_date", "first"),
            gaspar_event_end_date=("gaspar_end_date", "first"),
            gaspar_total_communes=("insee_com", "nunique"),
        )
        .reset_index()
    )

    diagnostics = {
        "raw_rows": int(len(raw)),
        "invalid_rows_dropped": invalid_rows,
        "duplicate_event_commune_rows_dropped": duplicate_rows,
        "canonical_rows": int(len(df)),
        "unique_gaspar_event_uids": int(df["gaspar_event_uid"].nunique()),
        "unique_gaspar_decrees": int(df["cod_nat_catnat"].nunique()),
        "unique_gaspar_communes": int(df["insee_com"].nunique()),
        "gaspar_decrees_with_multiple_date_pairs": int(
            (date_pair_counts["unique_date_pairs"] > 1).sum()
        ),
        "max_unique_date_pairs_within_one_decree": int(
            date_pair_counts["unique_date_pairs"].max()
        ),
    }
    return df, {
        "diagnostics": diagnostics,
        "event_stats": event_stats,
        "date_pair_counts": date_pair_counts,
    }


def compute_interval_overlap_days(
    start_left: pd.Series,
    end_left: pd.Series,
    start_right: pd.Series,
    end_right: pd.Series,
) -> pd.Series:
    overlap_start = start_left.where(start_left >= start_right, start_right)
    overlap_end = end_left.where(end_left <= end_right, end_right)
    overlap_days = (overlap_end - overlap_start).dt.days + 1
    return overlap_days.clip(lower=0)


def build_summary_table(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [{"metric": key, "value": value} for key, value in summary.items()]
    return pd.DataFrame(rows)


def join_unique_strings(series: pd.Series) -> str | pd.NA:
    values = []
    for value in pd.Series(series).dropna().astype(str):
        clean = value.strip()
        if clean and clean not in values:
            values.append(clean)
    if not values:
        return pd.NA
    return " | ".join(values)


def derive_department_code_series(series: pd.Series) -> pd.Series:
    normalized = normalize_insee_code_series(series)
    department_code = pd.Series(pd.NA, index=normalized.index, dtype="string")
    overseas_mask = normalized.str.match(r"^(97|98)\d", na=False)
    standard_mask = normalized.notna() & ~overseas_mask
    department_code.loc[overseas_mask] = normalized.loc[overseas_mask].str[:3]
    department_code.loc[standard_mask] = normalized.loc[standard_mask].str[:2]
    return department_code


def build_department_reference_from_lookup(
    france_lookup_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    lookup = read_table(france_lookup_path)
    required = {"insee_dep", "nuts3_code", "nuts3_name"}
    missing = required - set(lookup.columns)
    if missing:
        raise KeyError(
            f"France lookup input is missing required columns: {sorted(missing)}"
        )

    source = lookup[["insee_dep", "nuts3_code", "nuts3_name"]].copy()
    source = source.rename(columns={"insee_dep": "department_code"})
    source["department_code"] = source["department_code"].astype("string").str.strip()
    source["nuts3_code"] = source["nuts3_code"].astype("string").str.strip()
    source["nuts3_name"] = source["nuts3_name"].astype("string").str.strip()
    source = source.loc[source["department_code"].notna()].copy()
    if source.empty:
        empty = pd.DataFrame(
            columns=[
                "department_code",
                "dept_ref_nuts3_code",
                "dept_ref_nuts3_name",
                "dept_ref_unique_nuts3_codes",
            ]
        )
        return empty, {
            "department_reference_rows": 0,
            "departments_with_multiple_nuts3_codes": 0,
        }

    reference = (
        source.groupby("department_code", dropna=False)
        .agg(
            dept_ref_nuts3_code=("nuts3_code", join_unique_strings),
            dept_ref_nuts3_name=("nuts3_name", join_unique_strings),
            dept_ref_unique_nuts3_codes=(
                "nuts3_code",
                lambda s: int(pd.Series(s).dropna().astype(str).nunique()),
            ),
        )
        .reset_index()
    )
    diagnostics = {
        "department_reference_source": str(france_lookup_path),
        "department_reference_source_rows": int(len(source)),
        "department_reference_rows": int(len(reference)),
        "departments_with_multiple_nuts3_codes": int(
            reference["dept_ref_unique_nuts3_codes"].fillna(0).gt(1).sum()
        ),
    }
    return reference, diagnostics


def prepare_jrc_commune_events_flexible(
    jrc_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    jrc_df, meta = prepare_jrc_commune_events(jrc_path)
    jrc_df = jrc_df.copy()
    jrc_df["department_code"] = derive_department_code_series(jrc_df["insee_com"])

    department_stats = (
        jrc_df.groupby("jrc_event_id", dropna=False)
        .agg(jrc_total_departments=("department_code", "nunique"))
        .reset_index()
    )
    meta = dict(meta)
    meta["event_stats"] = meta["event_stats"].merge(
        department_stats,
        on="jrc_event_id",
        how="left",
        validate="1:1",
    )
    meta["diagnostics"] = dict(meta["diagnostics"])
    meta["diagnostics"]["unique_jrc_departments"] = int(jrc_df["department_code"].nunique())
    return jrc_df, meta


def prepare_gaspar_commune_events_flexible(
    gaspar_path: str | Path,
    sheet_name: str | int = 0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    gaspar_df, meta = prepare_gaspar_commune_events(gaspar_path, sheet_name=sheet_name)
    gaspar_df = gaspar_df.copy()
    gaspar_df["department_code"] = derive_department_code_series(gaspar_df["insee_com"])

    department_stats = (
        gaspar_df.groupby("gaspar_event_uid", dropna=False)
        .agg(gaspar_total_departments=("department_code", "nunique"))
        .reset_index()
    )
    meta = dict(meta)
    meta["event_stats"] = meta["event_stats"].merge(
        department_stats,
        on="gaspar_event_uid",
        how="left",
        validate="1:1",
    )
    meta["diagnostics"] = dict(meta["diagnostics"])
    meta["diagnostics"]["unique_gaspar_departments"] = int(
        gaspar_df["department_code"].nunique()
    )
    return gaspar_df, meta


def apply_flexible_date_rules(merged: pd.DataFrame, window_days: int) -> pd.DataFrame:
    merged = merged.copy()
    merged["start_diff_days"] = (merged["jrc_start_date"] - merged["gaspar_start_date"]).dt.days
    merged["end_diff_days"] = (merged["jrc_end_date"] - merged["gaspar_end_date"]).dt.days
    merged["abs_start_diff_days"] = merged["start_diff_days"].abs()
    merged["abs_end_diff_days"] = merged["end_diff_days"].abs()
    merged["total_abs_date_diff_days"] = (
        merged["abs_start_diff_days"] + merged["abs_end_diff_days"]
    )
    merged["exact_date_match"] = (
        merged["abs_start_diff_days"].eq(0) & merged["abs_end_diff_days"].eq(0)
    )

    merged["jrc_start_minus_gaspar_end_days"] = (
        merged["jrc_start_date"] - merged["gaspar_end_date"]
    ).dt.days
    merged["gaspar_start_minus_jrc_end_days"] = (
        merged["gaspar_start_date"] - merged["jrc_end_date"]
    ).dt.days
    merged["abs_jrc_start_minus_gaspar_end_days"] = (
        merged["jrc_start_minus_gaspar_end_days"].abs()
    )
    merged["abs_gaspar_start_minus_jrc_end_days"] = (
        merged["gaspar_start_minus_jrc_end_days"].abs()
    )

    merged["within_start_end_window"] = (
        merged["abs_start_diff_days"].le(window_days)
        & merged["abs_end_diff_days"].le(window_days)
    )
    merged["within_cross_start_end_window"] = (
        merged["abs_jrc_start_minus_gaspar_end_days"].le(window_days)
        & merged["abs_gaspar_start_minus_jrc_end_days"].le(window_days)
    )
    merged["window_expanded_interval_overlap"] = (
        merged["jrc_start_date"].le(merged["gaspar_end_date"] + pd.Timedelta(days=window_days))
        & merged["gaspar_start_date"].le(merged["jrc_end_date"] + pd.Timedelta(days=window_days))
    )
    merged["interval_overlap_days"] = compute_interval_overlap_days(
        merged["jrc_start_date"],
        merged["jrc_end_date"],
        merged["gaspar_start_date"],
        merged["gaspar_end_date"],
    )
    merged["flexible_date_match"] = (
        merged["within_start_end_window"]
        | merged["within_cross_start_end_window"]
        | merged["window_expanded_interval_overlap"]
    )

    merged["flexible_match_reason"] = pd.NA
    merged.loc[merged["window_expanded_interval_overlap"], "flexible_match_reason"] = (
        "expanded_interval_overlap"
    )
    merged.loc[merged["within_cross_start_end_window"], "flexible_match_reason"] = (
        "cross_start_end_window"
    )
    merged.loc[merged["within_start_end_window"], "flexible_match_reason"] = (
        "start_end_window"
    )
    merged.loc[merged["exact_date_match"], "flexible_match_reason"] = "exact_date"
    return merged


def build_commune_level_matches_flexible(
    jrc_df: pd.DataFrame,
    gaspar_df: pd.DataFrame,
    window_days: int,
) -> pd.DataFrame:
    jrc_cols = [
        col
        for col in [
            "jrc_event_id",
            "raster_file",
            "jrc_start_date",
            "jrc_end_date",
            "insee_com",
            "department_code",
            "jrc_commune_name",
            "nuts3_code",
            "nuts3_name",
            "max_depth_cm",
            "flooded_pixels",
            "flooded_area_m2",
        ]
        if col in jrc_df.columns
    ]
    gaspar_cols = [
        col
        for col in [
            "gaspar_event_uid",
            "cod_nat_catnat",
            "insee_com",
            "department_code",
            "gaspar_commune_name",
            "num_risque_jo",
            "lib_risque_jo",
            "gaspar_start_date",
            "gaspar_end_date",
            "dept_ref_nuts3_code",
            "dept_ref_nuts3_name",
        ]
        if col in gaspar_df.columns
    ]

    compare_jrc = jrc_df[jrc_cols].rename(columns={"department_code": "jrc_department_code"})
    compare_gaspar = gaspar_df[gaspar_cols].rename(
        columns={"department_code": "gaspar_department_code"}
    )

    merged = compare_jrc.merge(compare_gaspar, on="insee_com", how="inner", validate="m:m")
    if merged.empty:
        return merged

    merged = apply_flexible_date_rules(merged, window_days=window_days)
    matched = merged.loc[merged["flexible_date_match"]].copy()
    matched["date_window_days"] = window_days
    matched = matched.sort_values(
        by=[
            "jrc_event_id",
            "gaspar_event_uid",
            "insee_com",
            "total_abs_date_diff_days",
            "interval_overlap_days",
        ],
        ascending=[True, True, True, True, False],
        kind="stable",
    ).reset_index(drop=True)
    return matched


def build_jrc_department_events(jrc_df: pd.DataFrame) -> pd.DataFrame:
    agg_map: dict[str, tuple[str, Any]] = {
        "raster_file": ("raster_file", "first"),
        "jrc_nuts3_code": ("nuts3_code", join_unique_strings),
        "jrc_nuts3_name": ("nuts3_name", join_unique_strings),
        "jrc_communes_in_department": ("insee_com", "nunique"),
    }
    if "max_depth_cm" in jrc_df.columns:
        agg_map["jrc_max_depth_cm"] = ("max_depth_cm", "max")
    if "flooded_pixels" in jrc_df.columns:
        agg_map["jrc_flooded_pixels"] = ("flooded_pixels", "sum")
    if "flooded_area_m2" in jrc_df.columns:
        agg_map["jrc_flooded_area_m2"] = ("flooded_area_m2", "sum")

    jrc_department_events = (
        jrc_df.groupby(
            ["jrc_event_id", "department_code", "jrc_start_date", "jrc_end_date"],
            dropna=False,
        )
        .agg(**agg_map)
        .reset_index()
    )
    return jrc_department_events


def build_gaspar_department_events(gaspar_df: pd.DataFrame) -> pd.DataFrame:
    agg_map: dict[str, tuple[str, Any]] = {
        "cod_nat_catnat": ("cod_nat_catnat", "first"),
        "gaspar_communes_in_department": ("insee_com", "nunique"),
    }
    if "dept_ref_nuts3_code" in gaspar_df.columns:
        agg_map["dept_ref_nuts3_code"] = ("dept_ref_nuts3_code", "first")
    if "dept_ref_nuts3_name" in gaspar_df.columns:
        agg_map["dept_ref_nuts3_name"] = ("dept_ref_nuts3_name", "first")

    gaspar_department_events = (
        gaspar_df.groupby(
            ["gaspar_event_uid", "department_code", "gaspar_start_date", "gaspar_end_date"],
            dropna=False,
        )
        .agg(**agg_map)
        .reset_index()
    )
    return gaspar_department_events


def build_department_level_matches_flexible(
    jrc_department_events: pd.DataFrame,
    gaspar_department_events: pd.DataFrame,
    window_days: int,
) -> pd.DataFrame:
    compare_jrc = jrc_department_events.copy()
    compare_gaspar = gaspar_department_events.copy()

    merged = compare_jrc.merge(
        compare_gaspar,
        on="department_code",
        how="inner",
        validate="m:m",
        suffixes=("", "_gaspar"),
    )
    if merged.empty:
        return merged

    merged = apply_flexible_date_rules(merged, window_days=window_days)
    matched = merged.loc[merged["flexible_date_match"]].copy()
    matched["date_window_days"] = window_days
    matched = matched.sort_values(
        by=[
            "jrc_event_id",
            "gaspar_event_uid",
            "department_code",
            "total_abs_date_diff_days",
            "interval_overlap_days",
        ],
        ascending=[True, True, True, True, False],
        kind="stable",
    ).reset_index(drop=True)
    return matched


def build_match_scores(
    matches: pd.DataFrame,
    jrc_event_stats: pd.DataFrame,
    gaspar_event_stats: pd.DataFrame,
    unit_col: str,
    matched_unit_col: str,
    exact_match_col: str,
    jrc_total_units_col: str,
    gaspar_total_units_col: str,
) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()

    event_scores = (
        matches.groupby(
            [
                "jrc_event_id",
                "gaspar_event_uid",
                "cod_nat_catnat",
                "jrc_start_date",
                "jrc_end_date",
                "gaspar_start_date",
                "gaspar_end_date",
            ],
            dropna=False,
        )
        .agg(
            **{
                matched_unit_col: (unit_col, "nunique"),
                exact_match_col: ("exact_date_match", "sum"),
                "start_end_window_unit_matches": ("within_start_end_window", "sum"),
                "cross_start_end_window_unit_matches": ("within_cross_start_end_window", "sum"),
                "expanded_interval_overlap_unit_matches": (
                    "window_expanded_interval_overlap",
                    "sum",
                ),
                "mean_abs_start_diff_days": ("abs_start_diff_days", "mean"),
                "mean_abs_end_diff_days": ("abs_end_diff_days", "mean"),
                "mean_total_abs_date_diff_days": ("total_abs_date_diff_days", "mean"),
                "min_total_abs_date_diff_days": ("total_abs_date_diff_days", "min"),
                "max_interval_overlap_days": ("interval_overlap_days", "max"),
            }
        )
        .reset_index()
    )

    event_scores = event_scores.merge(jrc_event_stats, on="jrc_event_id", how="left", validate="m:1")
    event_scores = event_scores.merge(
        gaspar_event_stats,
        on="gaspar_event_uid",
        how="left",
        validate="m:1",
        suffixes=("", "_gaspar_stats"),
    )
    if "cod_nat_catnat_gaspar_stats" in event_scores.columns:
        event_scores["cod_nat_catnat"] = event_scores["cod_nat_catnat"].fillna(
            event_scores["cod_nat_catnat_gaspar_stats"]
        )
        event_scores = event_scores.drop(columns=["cod_nat_catnat_gaspar_stats"])

    event_scores["jrc_match_share"] = (
        event_scores[matched_unit_col] / event_scores[jrc_total_units_col]
    )
    event_scores["gaspar_match_share"] = (
        event_scores[matched_unit_col] / event_scores[gaspar_total_units_col]
    )
    return event_scores


def select_best_matches_generic(
    event_scores: pd.DataFrame,
    matched_unit_col: str,
    exact_match_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if event_scores.empty:
        return event_scores.copy(), event_scores.copy(), event_scores.copy()

    sort_cols = [
        matched_unit_col,
        exact_match_col,
        "jrc_match_share",
        "gaspar_match_share",
        "min_total_abs_date_diff_days",
        "mean_total_abs_date_diff_days",
        "gaspar_event_uid",
        "jrc_event_id",
    ]
    ascending = [False, False, False, False, True, True, True, True]

    ranked_for_jrc = event_scores.sort_values(sort_cols, ascending=ascending, kind="stable").copy()
    ranked_for_jrc["jrc_match_rank"] = ranked_for_jrc.groupby("jrc_event_id").cumcount() + 1
    best_gaspar_per_jrc = ranked_for_jrc[ranked_for_jrc["jrc_match_rank"] == 1].copy()

    ranked_for_gaspar = event_scores.sort_values(sort_cols, ascending=ascending, kind="stable").copy()
    ranked_for_gaspar["gaspar_match_rank"] = (
        ranked_for_gaspar.groupby("gaspar_event_uid").cumcount() + 1
    )
    best_jrc_per_gaspar = ranked_for_gaspar[ranked_for_gaspar["gaspar_match_rank"] == 1].copy()

    best_pair_keys = set(
        zip(best_gaspar_per_jrc["jrc_event_id"], best_gaspar_per_jrc["gaspar_event_uid"])
    )
    best_jrc_pair_keys = set(
        zip(best_jrc_per_gaspar["jrc_event_id"], best_jrc_per_gaspar["gaspar_event_uid"])
    )

    reciprocal = ranked_for_jrc.copy()
    reciprocal["reciprocal_best_match"] = reciprocal.apply(
        lambda row: (row["jrc_event_id"], row["gaspar_event_uid"]) in best_pair_keys
        and (row["jrc_event_id"], row["gaspar_event_uid"]) in best_jrc_pair_keys,
        axis=1,
    )
    return reciprocal, best_gaspar_per_jrc, best_jrc_per_gaspar


def build_unmatched_tables_generic(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    matches: pd.DataFrame,
    left_event_col: str,
    right_event_col: str,
    unit_col: str,
    left_start_col: str,
    left_end_col: str,
    right_start_col: str,
    right_end_col: str,
    left_event_stats: pd.DataFrame,
    right_event_stats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if matches.empty:
        return (
            left_df.copy(),
            right_df.copy(),
            left_event_stats.copy(),
            right_event_stats.copy(),
        )

    matched_left_keys = matches[
        [left_event_col, unit_col, left_start_col, left_end_col]
    ].drop_duplicates()
    matched_right_keys = matches[
        [right_event_col, unit_col, right_start_col, right_end_col]
    ].drop_duplicates()

    unmatched_left = (
        left_df.merge(
            matched_left_keys,
            on=[left_event_col, unit_col, left_start_col, left_end_col],
            how="left",
            indicator=True,
        )
        .loc[lambda df: df["_merge"].eq("left_only")]
        .drop(columns=["_merge"])
        .reset_index(drop=True)
    )
    unmatched_right = (
        right_df.merge(
            matched_right_keys,
            on=[right_event_col, unit_col, right_start_col, right_end_col],
            how="left",
            indicator=True,
        )
        .loc[lambda df: df["_merge"].eq("left_only")]
        .drop(columns=["_merge"])
        .reset_index(drop=True)
    )

    matched_left_event_ids = matches[left_event_col].drop_duplicates()
    matched_right_event_ids = matches[right_event_col].drop_duplicates()
    unmatched_left_events = left_event_stats.loc[
        ~left_event_stats[left_event_col].isin(matched_left_event_ids)
    ].reset_index(drop=True)
    unmatched_right_events = right_event_stats.loc[
        ~right_event_stats[right_event_col].isin(matched_right_event_ids)
    ].reset_index(drop=True)

    return unmatched_left, unmatched_right, unmatched_left_events, unmatched_right_events


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Flexible France JRC vs Gaspar comparison using INSEE commune codes, "
            "a broader date window, and department-level rollups."
        )
    )
    parser.add_argument(
        "--jrc-file",
        default="data/processed/france_lau_insee_documentation/events_fr_insee_long.csv",
        help=(
            "Path to the France JRC commune-event table from france_lau_to_insee.py. "
            "Default: data/processed/france_lau_insee_documentation/events_fr_insee_long.csv"
        ),
    )
    parser.add_argument(
        "--gaspar-file",
        default="data/processed/Gaspar_2015_2024.xlsx",
        help="Path to the cleaned Gaspar Excel workbook.",
    )
    parser.add_argument(
        "--france-lookup-file",
        default="data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv",
        help=(
            "Path to the full France LAU to INSEE lookup used to attach a complete "
            "department to NUTS3 reference for Gaspar. Default: "
            "data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv"
        ),
    )
    parser.add_argument(
        "--sheet-name",
        default="Gaspar20152024FloodsClean",
        help="Sheet name to read from the Gaspar workbook. Default: Gaspar20152024FloodsClean",
    )
    parser.add_argument(
        "--date-window-days",
        type=int,
        default=7,
        help="Flexible matching window in days for all date rules. Default: 7.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/processed/jrc_gaspar_comparison_flexible_7d",
        help=(
            "Output directory for commune and department match tables, workbook, "
            "and diagnostics. Default: data/processed/"
            "jrc_gaspar_comparison_flexible_7d"
        ),
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    details_dir = out_dir / "details"
    details_dir.mkdir(parents=True, exist_ok=True)
    window_tag = f"{args.date_window_days}d"

    print("Reading JRC France commune-event table...")
    jrc_df, jrc_meta = prepare_jrc_commune_events_flexible(args.jrc_file)
    print(json.dumps(jrc_meta["diagnostics"], indent=2, ensure_ascii=False))

    print("Reading cleaned Gaspar flood sheet...")
    gaspar_df, gaspar_meta = prepare_gaspar_commune_events_flexible(
        args.gaspar_file,
        args.sheet_name,
    )
    print(json.dumps(gaspar_meta["diagnostics"], indent=2, ensure_ascii=False))

    print("Reading full France department -> NUTS3 reference...")
    department_reference, department_reference_diagnostics = build_department_reference_from_lookup(
        args.france_lookup_file
    )
    if not department_reference.empty:
        gaspar_df = gaspar_df.merge(
            department_reference,
            on="department_code",
            how="left",
            validate="m:1",
        )

    print(f"Building commune-level flexible {args.date_window_days}-day matches...")
    commune_matches = build_commune_level_matches_flexible(
        jrc_df=jrc_df,
        gaspar_df=gaspar_df,
        window_days=args.date_window_days,
    )
    print(f"Commune-level flexible matches: {len(commune_matches):,}")

    print("Aggregating commune-level event match scores...")
    commune_event_scores = build_match_scores(
        matches=commune_matches,
        jrc_event_stats=jrc_meta["event_stats"],
        gaspar_event_stats=gaspar_meta["event_stats"],
        unit_col="insee_com",
        matched_unit_col="matched_communes",
        exact_match_col="exact_date_commune_matches",
        jrc_total_units_col="jrc_total_communes",
        gaspar_total_units_col="gaspar_total_communes",
    )
    (
        commune_event_scores_ranked,
        best_gaspar_per_jrc_commune,
        best_jrc_per_gaspar_commune,
    ) = select_best_matches_generic(
        commune_event_scores,
        matched_unit_col="matched_communes",
        exact_match_col="exact_date_commune_matches",
    )

    (
        unmatched_jrc_communes,
        unmatched_gaspar_communes,
        unmatched_jrc_events_commune_level,
        unmatched_gaspar_events_commune_level,
    ) = build_unmatched_tables_generic(
        left_df=jrc_df,
        right_df=gaspar_df,
        matches=commune_matches,
        left_event_col="jrc_event_id",
        right_event_col="gaspar_event_uid",
        unit_col="insee_com",
        left_start_col="jrc_start_date",
        left_end_col="jrc_end_date",
        right_start_col="gaspar_start_date",
        right_end_col="gaspar_end_date",
        left_event_stats=jrc_meta["event_stats"],
        right_event_stats=gaspar_meta["event_stats"],
    )

    print("Building department-level canonical tables...")
    jrc_department_events = build_jrc_department_events(jrc_df)
    gaspar_department_events = build_gaspar_department_events(gaspar_df)

    print(f"Building department-level flexible {args.date_window_days}-day matches...")
    department_matches = build_department_level_matches_flexible(
        jrc_department_events=jrc_department_events,
        gaspar_department_events=gaspar_department_events,
        window_days=args.date_window_days,
    )
    print(f"Department-level flexible matches: {len(department_matches):,}")

    print("Aggregating department-level event match scores...")
    department_event_scores = build_match_scores(
        matches=department_matches,
        jrc_event_stats=jrc_meta["event_stats"],
        gaspar_event_stats=gaspar_meta["event_stats"],
        unit_col="department_code",
        matched_unit_col="matched_departments",
        exact_match_col="exact_date_department_matches",
        jrc_total_units_col="jrc_total_departments",
        gaspar_total_units_col="gaspar_total_departments",
    )
    (
        department_event_scores_ranked,
        best_gaspar_per_jrc_department,
        best_jrc_per_gaspar_department,
    ) = select_best_matches_generic(
        department_event_scores,
        matched_unit_col="matched_departments",
        exact_match_col="exact_date_department_matches",
    )

    (
        unmatched_jrc_departments,
        unmatched_gaspar_departments,
        unmatched_jrc_events_department_level,
        unmatched_gaspar_events_department_level,
    ) = build_unmatched_tables_generic(
        left_df=jrc_department_events,
        right_df=gaspar_department_events,
        matches=department_matches,
        left_event_col="jrc_event_id",
        right_event_col="gaspar_event_uid",
        unit_col="department_code",
        left_start_col="jrc_start_date",
        left_end_col="jrc_end_date",
        right_start_col="gaspar_start_date",
        right_end_col="gaspar_end_date",
        left_event_stats=jrc_meta["event_stats"],
        right_event_stats=gaspar_meta["event_stats"],
    )

    summary = {
        "date_window_days": args.date_window_days,
        "jrc_canonical_commune_rows": int(len(jrc_df)),
        "jrc_unique_events": int(jrc_df["jrc_event_id"].nunique()),
        "jrc_unique_communes": int(jrc_df["insee_com"].nunique()),
        "jrc_unique_departments": int(jrc_df["department_code"].nunique()),
        "gaspar_canonical_commune_rows": int(len(gaspar_df)),
        "gaspar_unique_event_uids": int(gaspar_df["gaspar_event_uid"].nunique()),
        "gaspar_unique_decrees": int(gaspar_df["cod_nat_catnat"].nunique()),
        "gaspar_unique_communes": int(gaspar_df["insee_com"].nunique()),
        "gaspar_unique_departments": int(gaspar_df["department_code"].nunique()),
        "commune_level_matches": int(len(commune_matches)),
        "matched_jrc_commune_events": int(
            commune_matches[["jrc_event_id", "insee_com", "jrc_start_date", "jrc_end_date"]]
            .drop_duplicates()
            .shape[0]
        ) if not commune_matches.empty else 0,
        "matched_gaspar_commune_events": int(
            commune_matches[
                ["gaspar_event_uid", "insee_com", "gaspar_start_date", "gaspar_end_date"]
            ]
            .drop_duplicates()
            .shape[0]
        ) if not commune_matches.empty else 0,
        "matched_jrc_events_commune_level": int(commune_matches["jrc_event_id"].nunique())
        if not commune_matches.empty
        else 0,
        "matched_gaspar_event_uids_commune_level": int(
            commune_matches["gaspar_event_uid"].nunique()
        ) if not commune_matches.empty else 0,
        "department_level_matches": int(len(department_matches)),
        "matched_jrc_department_events": int(
            department_matches[
                ["jrc_event_id", "department_code", "jrc_start_date", "jrc_end_date"]
            ]
            .drop_duplicates()
            .shape[0]
        ) if not department_matches.empty else 0,
        "matched_gaspar_department_events": int(
            department_matches[
                [
                    "gaspar_event_uid",
                    "department_code",
                    "gaspar_start_date",
                    "gaspar_end_date",
                ]
            ]
            .drop_duplicates()
            .shape[0]
        ) if not department_matches.empty else 0,
        "matched_jrc_events_department_level": int(
            department_matches["jrc_event_id"].nunique()
        ) if not department_matches.empty else 0,
        "matched_gaspar_event_uids_department_level": int(
            department_matches["gaspar_event_uid"].nunique()
        ) if not department_matches.empty else 0,
        "commune_level_reciprocal_best_event_pairs": int(
            commune_event_scores_ranked["reciprocal_best_match"].fillna(False).sum()
        ) if not commune_event_scores_ranked.empty else 0,
        "department_level_reciprocal_best_event_pairs": int(
            department_event_scores_ranked["reciprocal_best_match"].fillna(False).sum()
        ) if not department_event_scores_ranked.empty else 0,
    }
    summary_table = build_summary_table(summary)
    coverage_overview = build_coverage_overview(
        [
            {
                "level": "commune",
                "measurement": "unique_events",
                "jrc_matched": int(summary["matched_jrc_events_commune_level"]),
                "jrc_total": int(summary["jrc_unique_events"]),
                "jrc_match_share": (
                    float(summary["matched_jrc_events_commune_level"])
                    / float(summary["jrc_unique_events"])
                    if summary["jrc_unique_events"]
                    else 0.0
                ),
                "gaspar_matched": int(summary["matched_gaspar_event_uids_commune_level"]),
                "gaspar_total": int(summary["gaspar_unique_event_uids"]),
                "gaspar_match_share": (
                    float(summary["matched_gaspar_event_uids_commune_level"])
                    / float(summary["gaspar_unique_event_uids"])
                    if summary["gaspar_unique_event_uids"]
                    else 0.0
                ),
            },
            {
                "level": "commune",
                "measurement": "canonical_rows",
                "jrc_matched": int(len(jrc_df) - len(unmatched_jrc_communes)),
                "jrc_total": int(len(jrc_df)),
                "jrc_match_share": (
                    float(len(jrc_df) - len(unmatched_jrc_communes)) / float(len(jrc_df))
                    if len(jrc_df)
                    else 0.0
                ),
                "gaspar_matched": int(len(gaspar_df) - len(unmatched_gaspar_communes)),
                "gaspar_total": int(len(gaspar_df)),
                "gaspar_match_share": (
                    float(len(gaspar_df) - len(unmatched_gaspar_communes)) / float(len(gaspar_df))
                    if len(gaspar_df)
                    else 0.0
                ),
            },
            {
                "level": "department",
                "measurement": "unique_events",
                "jrc_matched": int(summary["matched_jrc_events_department_level"]),
                "jrc_total": int(summary["jrc_unique_events"]),
                "jrc_match_share": (
                    float(summary["matched_jrc_events_department_level"])
                    / float(summary["jrc_unique_events"])
                    if summary["jrc_unique_events"]
                    else 0.0
                ),
                "gaspar_matched": int(summary["matched_gaspar_event_uids_department_level"]),
                "gaspar_total": int(summary["gaspar_unique_event_uids"]),
                "gaspar_match_share": (
                    float(summary["matched_gaspar_event_uids_department_level"])
                    / float(summary["gaspar_unique_event_uids"])
                    if summary["gaspar_unique_event_uids"]
                    else 0.0
                ),
            },
            {
                "level": "department",
                "measurement": "canonical_rows",
                "jrc_matched": int(len(jrc_department_events) - len(unmatched_jrc_departments)),
                "jrc_total": int(len(jrc_department_events)),
                "jrc_match_share": (
                    float(len(jrc_department_events) - len(unmatched_jrc_departments))
                    / float(len(jrc_department_events))
                    if len(jrc_department_events)
                    else 0.0
                ),
                "gaspar_matched": int(
                    len(gaspar_department_events) - len(unmatched_gaspar_departments)
                ),
                "gaspar_total": int(len(gaspar_department_events)),
                "gaspar_match_share": (
                    float(len(gaspar_department_events) - len(unmatched_gaspar_departments))
                    / float(len(gaspar_department_events))
                    if len(gaspar_department_events)
                    else 0.0
                ),
            },
        ]
    )
    best_match_overview_commune = build_best_match_overview(
        best_matches=best_gaspar_per_jrc_commune,
        ranked_scores=commune_event_scores_ranked,
        matched_col="matched_communes",
        exact_col="exact_date_commune_matches",
    )
    best_match_overview_department = build_best_match_overview(
        best_matches=best_gaspar_per_jrc_department,
        ranked_scores=department_event_scores_ranked,
        matched_col="matched_departments",
        exact_col="exact_date_department_matches",
    )
    comparison_guide = build_output_guide_markdown(
        title="France JRC vs Gaspar Flexible Comparison (7-day variant)",
        window_days=args.date_window_days,
        top_level_files=[
            "comparison_guide.md",
            "comparison_summary.csv",
            "comparison_summary.xlsx",
            "coverage_overview.csv",
            "coverage_overview.xlsx",
            "best_match_overview_commune.csv",
            "best_match_overview_commune.xlsx",
            "best_match_overview_department.csv",
            "best_match_overview_department.xlsx",
            "jrc_gaspar_comparison_flexible.xlsx",
            "plots/",
            "details/",
        ],
        details_dir_name="details",
        coverage_overview=coverage_overview,
    )
    detail_file_names = [
        "jrc_france_commune_events_canonical.csv",
        "gaspar_commune_events_canonical.csv",
        f"commune_event_matches_flexible_{window_tag}.csv",
        "commune_event_match_scores.csv",
        "best_gaspar_match_per_jrc_event_commune.csv",
        "best_jrc_match_per_gaspar_event_commune.csv",
        "unmatched_jrc_commune_events.csv",
        "unmatched_gaspar_commune_events.csv",
        "unmatched_jrc_events_commune_level.csv",
        "unmatched_gaspar_events_commune_level.csv",
        "department_reference_from_france_lookup.csv",
        "jrc_france_department_events_canonical.csv",
        "gaspar_department_events_canonical.csv",
        f"department_event_matches_flexible_{window_tag}.csv",
        "department_event_match_scores.csv",
        "best_gaspar_match_per_jrc_event_department.csv",
        "best_jrc_match_per_gaspar_event_department.csv",
        "unmatched_jrc_department_events.csv",
        "unmatched_gaspar_department_events.csv",
        "unmatched_jrc_events_department_level.csv",
        "unmatched_gaspar_events_department_level.csv",
        f"commune_event_matches_flexible_{window_tag}.parquet",
        "commune_event_match_scores.parquet",
        f"department_event_matches_flexible_{window_tag}.parquet",
        "department_event_match_scores.parquet",
        "comparison_diagnostics.json",
    ]

    print("Writing outputs...")
    relocate_existing_detail_files(out_dir, details_dir, detail_file_names)
    legacy_department_reference_path = details_dir / "department_reference_from_jrc.csv"
    if legacy_department_reference_path.exists():
        legacy_department_reference_path.unlink()
    write_csv(out_dir / "comparison_summary.csv", summary_table)
    write_csv(out_dir / "coverage_overview.csv", coverage_overview)
    write_csv(out_dir / "best_match_overview_commune.csv", best_match_overview_commune)
    write_csv(
        out_dir / "best_match_overview_department.csv",
        best_match_overview_department,
    )
    write_single_sheet_excel(out_dir / "comparison_summary.xlsx", "summary", summary_table)
    write_single_sheet_excel(out_dir / "coverage_overview.xlsx", "coverage", coverage_overview)
    write_single_sheet_excel(
        out_dir / "best_match_overview_commune.xlsx",
        "best_match_commune",
        best_match_overview_commune,
    )
    write_single_sheet_excel(
        out_dir / "best_match_overview_department.xlsx",
        "best_match_department",
        best_match_overview_department,
    )
    write_markdown(out_dir / "comparison_guide.md", comparison_guide)

    write_csv(details_dir / "jrc_france_commune_events_canonical.csv", jrc_df)
    write_csv(details_dir / "gaspar_commune_events_canonical.csv", gaspar_df)
    write_csv(
        details_dir / f"commune_event_matches_flexible_{window_tag}.csv",
        commune_matches,
    )
    write_csv(details_dir / "commune_event_match_scores.csv", commune_event_scores_ranked)
    write_csv(
        details_dir / "best_gaspar_match_per_jrc_event_commune.csv",
        best_gaspar_per_jrc_commune,
    )
    write_csv(
        details_dir / "best_jrc_match_per_gaspar_event_commune.csv",
        best_jrc_per_gaspar_commune,
    )
    write_csv(details_dir / "unmatched_jrc_commune_events.csv", unmatched_jrc_communes)
    write_csv(details_dir / "unmatched_gaspar_commune_events.csv", unmatched_gaspar_communes)
    write_csv(
        details_dir / "unmatched_jrc_events_commune_level.csv",
        unmatched_jrc_events_commune_level,
    )
    write_csv(
        details_dir / "unmatched_gaspar_events_commune_level.csv",
        unmatched_gaspar_events_commune_level,
    )

    write_csv(
        details_dir / "department_reference_from_france_lookup.csv",
        department_reference,
    )
    write_csv(details_dir / "jrc_france_department_events_canonical.csv", jrc_department_events)
    write_csv(details_dir / "gaspar_department_events_canonical.csv", gaspar_department_events)
    write_csv(
        details_dir / f"department_event_matches_flexible_{window_tag}.csv",
        department_matches,
    )
    write_csv(details_dir / "department_event_match_scores.csv", department_event_scores_ranked)
    write_csv(
        details_dir / "best_gaspar_match_per_jrc_event_department.csv",
        best_gaspar_per_jrc_department,
    )
    write_csv(
        details_dir / "best_jrc_match_per_gaspar_event_department.csv",
        best_jrc_per_gaspar_department,
    )
    write_csv(details_dir / "unmatched_jrc_department_events.csv", unmatched_jrc_departments)
    write_csv(
        details_dir / "unmatched_gaspar_department_events.csv",
        unmatched_gaspar_departments,
    )
    write_csv(
        details_dir / "unmatched_jrc_events_department_level.csv",
        unmatched_jrc_events_department_level,
    )
    write_csv(
        details_dir / "unmatched_gaspar_events_department_level.csv",
        unmatched_gaspar_events_department_level,
    )

    parquet_outputs = {
        f"commune_event_matches_flexible_{window_tag}": maybe_write_parquet(
            details_dir / f"commune_event_matches_flexible_{window_tag}.parquet",
            commune_matches,
        ),
        "commune_event_match_scores": maybe_write_parquet(
            details_dir / "commune_event_match_scores.parquet",
            commune_event_scores_ranked,
        ),
        f"department_event_matches_flexible_{window_tag}": maybe_write_parquet(
            details_dir / f"department_event_matches_flexible_{window_tag}.parquet",
            department_matches,
        ),
        "department_event_match_scores": maybe_write_parquet(
            details_dir / "department_event_match_scores.parquet",
            department_event_scores_ranked,
        ),
    }

    excel_status = write_excel_workbook(
        out_dir / "jrc_gaspar_comparison_flexible.xlsx",
        [
            ("summary", summary_table),
            ("coverage", coverage_overview),
            ("best_match_commune", best_match_overview_commune),
            ("best_match_dept", best_match_overview_department),
        ],
    )

    diagnostics = {
        "summary": summary,
        "jrc_diagnostics": jrc_meta["diagnostics"],
        "gaspar_diagnostics": gaspar_meta["diagnostics"],
        "department_reference_diagnostics": department_reference_diagnostics,
        "parquet_outputs": parquet_outputs,
        "excel_status": excel_status,
        "notes": {
            "gaspar_event_uid_definition": "cod_nat_catnat + dat_deb + dat_fin",
            "flexible_match_rule": (
                "same normalized INSEE or department code AND "
                "((abs(start-start) <= window AND abs(end-end) <= window) OR "
                "(abs(jrc_start-gaspar_end) <= window AND "
                "abs(gaspar_start-jrc_end) <= window) OR "
                "expanded interval overlap within the same window)"
            ),
            "department_level_note": (
                "Department outputs use French department codes derived from "
                "commune INSEE codes. Gaspar department rows receive NUTS3 "
                "reference labels from the full France LAU -> INSEE lookup, not "
                "only from departments present in JRC event coverage."
            ),
        },
    }
    (details_dir / "comparison_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Done.")
    print(f"Top-level guide: {out_dir / 'comparison_guide.md'}")
    print(f"Detailed audit tables: {details_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
