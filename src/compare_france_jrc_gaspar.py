"""
Compare France JRC flood commune-events against the cleaned Gaspar flood table.

Comparison logic:
- normalize INSEE commune codes on both sources
- use the France JRC commune-event table as produced by france_lau_to_insee.py
- use the cleaned Gaspar sheet from Gaspar_2015_2024.xlsx
- match first on commune code
- then match on event dates with a flexible window on both start and end dates

Important Gaspar nuance:
- ``cod_nat_catnat`` alone is not a reliable event grain for this comparison,
  because the same code can appear with different ``dat_deb`` / ``dat_fin``
  pairs across communes
- therefore this script defines a Gaspar event key as:
  ``cod_nat_catnat + dat_deb + dat_fin``
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
        df.get("commune_name_adminexpress", df.get("lau_name", pd.Series(pd.NA, index=df.index)))
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
    df = df.sort_values(key_cols, kind="stable").drop_duplicates(subset=key_cols).reset_index(drop=True)

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
    df = df.sort_values(key_cols, kind="stable").drop_duplicates(subset=key_cols).reset_index(drop=True)

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
        "gaspar_decrees_with_multiple_date_pairs": int((date_pair_counts["unique_date_pairs"] > 1).sum()),
        "max_unique_date_pairs_within_one_decree": int(date_pair_counts["unique_date_pairs"].max()),
    }
    return df, {"diagnostics": diagnostics, "event_stats": event_stats, "date_pair_counts": date_pair_counts}


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


def build_commune_level_matches(
    jrc_df: pd.DataFrame,
    gaspar_df: pd.DataFrame,
    window_days: int,
) -> pd.DataFrame:
    compare_jrc = jrc_df[
        [
            "jrc_event_id",
            "raster_file",
            "jrc_start_date",
            "jrc_end_date",
            "insee_com",
            "jrc_commune_name",
            "nuts3_code",
            "nuts3_name",
            "max_depth_cm",
            "flooded_pixels",
            "flooded_area_m2",
        ]
    ].copy()
    compare_gaspar = gaspar_df[
        [
            "gaspar_event_uid",
            "cod_nat_catnat",
            "insee_com",
            "gaspar_commune_name",
            "num_risque_jo",
            "lib_risque_jo",
            "gaspar_start_date",
            "gaspar_end_date",
        ]
    ].copy()

    merged = compare_jrc.merge(compare_gaspar, on="insee_com", how="inner", validate="m:m")
    if merged.empty:
        return merged

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
    merged["within_7d_start_end_window"] = (
        merged["abs_start_diff_days"].le(window_days)
        & merged["abs_end_diff_days"].le(window_days)
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

    matched = merged.loc[merged["within_7d_start_end_window"]].copy()
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


def build_event_level_match_scores(
    commune_matches: pd.DataFrame,
    jrc_event_stats: pd.DataFrame,
    gaspar_event_stats: pd.DataFrame,
) -> pd.DataFrame:
    if commune_matches.empty:
        return pd.DataFrame()

    event_scores = (
        commune_matches.groupby(
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
            matched_communes=("insee_com", "nunique"),
            exact_date_commune_matches=("exact_date_match", "sum"),
            mean_abs_start_diff_days=("abs_start_diff_days", "mean"),
            mean_abs_end_diff_days=("abs_end_diff_days", "mean"),
            mean_total_abs_date_diff_days=("total_abs_date_diff_days", "mean"),
            min_total_abs_date_diff_days=("total_abs_date_diff_days", "min"),
            max_interval_overlap_days=("interval_overlap_days", "max"),
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
        event_scores["matched_communes"] / event_scores["jrc_total_communes"]
    )
    event_scores["gaspar_match_share"] = (
        event_scores["matched_communes"] / event_scores["gaspar_total_communes"]
    )
    return event_scores


def select_best_matches(
    event_scores: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if event_scores.empty:
        return event_scores.copy(), event_scores.copy(), event_scores.copy()

    sort_cols = [
        "matched_communes",
        "exact_date_commune_matches",
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
    ranked_for_gaspar["gaspar_match_rank"] = ranked_for_gaspar.groupby("gaspar_event_uid").cumcount() + 1
    best_jrc_per_gaspar = ranked_for_gaspar[ranked_for_gaspar["gaspar_match_rank"] == 1].copy()

    reciprocal = ranked_for_jrc.merge(
        best_jrc_per_gaspar[["jrc_event_id", "gaspar_event_uid"]],
        on=["jrc_event_id", "gaspar_event_uid"],
        how="left",
        indicator=True,
    )
    reciprocal["reciprocal_best_match"] = reciprocal["_merge"].eq("both")
    reciprocal = reciprocal.drop(columns=["_merge"])

    best_pair_keys = set(
        zip(
            best_gaspar_per_jrc["jrc_event_id"],
            best_gaspar_per_jrc["gaspar_event_uid"],
        )
    )
    best_jrc_pair_keys = set(
        zip(
            best_jrc_per_gaspar["jrc_event_id"],
            best_jrc_per_gaspar["gaspar_event_uid"],
        )
    )
    reciprocal["reciprocal_best_match"] = reciprocal.apply(
        lambda row: (row["jrc_event_id"], row["gaspar_event_uid"]) in best_pair_keys
        and (row["jrc_event_id"], row["gaspar_event_uid"]) in best_jrc_pair_keys,
        axis=1,
    )
    return reciprocal, best_gaspar_per_jrc, best_jrc_per_gaspar


def build_unmatched_tables(
    jrc_df: pd.DataFrame,
    gaspar_df: pd.DataFrame,
    commune_matches: pd.DataFrame,
    jrc_event_stats: pd.DataFrame,
    gaspar_event_stats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if commune_matches.empty:
        return (
            jrc_df.copy(),
            gaspar_df.copy(),
            jrc_event_stats.copy(),
            gaspar_event_stats.copy(),
        )

    matched_jrc_keys = commune_matches[
        ["jrc_event_id", "insee_com", "jrc_start_date", "jrc_end_date"]
    ].drop_duplicates()
    matched_gaspar_keys = commune_matches[
        ["gaspar_event_uid", "insee_com", "gaspar_start_date", "gaspar_end_date"]
    ].drop_duplicates()

    unmatched_jrc = (
        jrc_df.merge(
            matched_jrc_keys,
            on=["jrc_event_id", "insee_com", "jrc_start_date", "jrc_end_date"],
            how="left",
            indicator=True,
        )
        .loc[lambda df: df["_merge"].eq("left_only")]
        .drop(columns=["_merge"])
        .reset_index(drop=True)
    )
    unmatched_gaspar = (
        gaspar_df.merge(
            matched_gaspar_keys,
            on=["gaspar_event_uid", "insee_com", "gaspar_start_date", "gaspar_end_date"],
            how="left",
            indicator=True,
        )
        .loc[lambda df: df["_merge"].eq("left_only")]
        .drop(columns=["_merge"])
        .reset_index(drop=True)
    )

    matched_jrc_event_ids = commune_matches["jrc_event_id"].drop_duplicates()
    matched_gaspar_event_uids = commune_matches["gaspar_event_uid"].drop_duplicates()
    unmatched_jrc_events = jrc_event_stats.loc[
        ~jrc_event_stats["jrc_event_id"].isin(matched_jrc_event_ids)
    ].reset_index(drop=True)
    unmatched_gaspar_events = gaspar_event_stats.loc[
        ~gaspar_event_stats["gaspar_event_uid"].isin(matched_gaspar_event_uids)
    ].reset_index(drop=True)

    return unmatched_jrc, unmatched_gaspar, unmatched_jrc_events, unmatched_gaspar_events


def build_summary_table(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [{"metric": key, "value": value} for key, value in summary.items()]
    return pd.DataFrame(rows)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare France JRC commune-events against the cleaned Gaspar flood table "
            "using INSEE commune codes and a flexible start/end date window."
        )
    )
    parser.add_argument(
        "--jrc-file",
        default="data/france_lau_insee_documentation/events_fr_insee_long.csv",
        help=(
            "Path to the France JRC commune-event table from france_lau_to_insee.py. "
            "Default: data/france_lau_insee_documentation/events_fr_insee_long.csv"
        ),
    )
    parser.add_argument(
        "--gaspar-file",
        default="data/processed/Gaspar_2015_2024.xlsx",
        help="Path to the cleaned Gaspar Excel workbook.",
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
        help="Flexible matching window in days for both start and end dates. Default: 7.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/processed/flood_outputs/jrc_gaspar_comparison_7d",
        help=(
            "Output directory for canonical tables, match tables, workbook, and diagnostics. "
            "Default: data/processed/flood_outputs/jrc_gaspar_comparison_7d"
        ),
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Reading JRC France commune-event table...")
    jrc_df, jrc_meta = prepare_jrc_commune_events(args.jrc_file)
    print(json.dumps(jrc_meta["diagnostics"], indent=2, ensure_ascii=False))

    print("Reading cleaned Gaspar flood sheet...")
    gaspar_df, gaspar_meta = prepare_gaspar_commune_events(args.gaspar_file, args.sheet_name)
    print(json.dumps(gaspar_meta["diagnostics"], indent=2, ensure_ascii=False))

    print("Building commune-level 7-day matches...")
    commune_matches = build_commune_level_matches(
        jrc_df=jrc_df,
        gaspar_df=gaspar_df,
        window_days=args.date_window_days,
    )
    print(f"Commune-level candidate matches: {len(commune_matches):,}")

    print("Aggregating to event-level match scores...")
    event_scores = build_event_level_match_scores(
        commune_matches=commune_matches,
        jrc_event_stats=jrc_meta["event_stats"],
        gaspar_event_stats=gaspar_meta["event_stats"],
    )
    event_scores_ranked, best_gaspar_per_jrc, best_jrc_per_gaspar = select_best_matches(event_scores)

    unmatched_jrc, unmatched_gaspar, unmatched_jrc_events, unmatched_gaspar_events = build_unmatched_tables(
        jrc_df=jrc_df,
        gaspar_df=gaspar_df,
        commune_matches=commune_matches,
        jrc_event_stats=jrc_meta["event_stats"],
        gaspar_event_stats=gaspar_meta["event_stats"],
    )

    summary = {
        "date_window_days": args.date_window_days,
        "jrc_canonical_rows": int(len(jrc_df)),
        "jrc_unique_events": int(jrc_df["jrc_event_id"].nunique()),
        "jrc_unique_communes": int(jrc_df["insee_com"].nunique()),
        "gaspar_canonical_rows": int(len(gaspar_df)),
        "gaspar_unique_event_uids": int(gaspar_df["gaspar_event_uid"].nunique()),
        "gaspar_unique_decrees": int(gaspar_df["cod_nat_catnat"].nunique()),
        "gaspar_unique_communes": int(gaspar_df["insee_com"].nunique()),
        "commune_level_matches": int(len(commune_matches)),
        "matched_jrc_commune_events": int(
            commune_matches[["jrc_event_id", "insee_com", "jrc_start_date", "jrc_end_date"]]
            .drop_duplicates()
            .shape[0]
        ) if not commune_matches.empty else 0,
        "matched_gaspar_commune_events": int(
            commune_matches[["gaspar_event_uid", "insee_com", "gaspar_start_date", "gaspar_end_date"]]
            .drop_duplicates()
            .shape[0]
        ) if not commune_matches.empty else 0,
        "matched_jrc_events": int(commune_matches["jrc_event_id"].nunique()) if not commune_matches.empty else 0,
        "matched_gaspar_event_uids": int(commune_matches["gaspar_event_uid"].nunique()) if not commune_matches.empty else 0,
        "unmatched_jrc_commune_events": int(len(unmatched_jrc)),
        "unmatched_gaspar_commune_events": int(len(unmatched_gaspar)),
        "unmatched_jrc_events": int(len(unmatched_jrc_events)),
        "unmatched_gaspar_event_uids": int(len(unmatched_gaspar_events)),
        "reciprocal_best_event_pairs": int(
            event_scores_ranked["reciprocal_best_match"].fillna(False).sum()
        ) if not event_scores_ranked.empty else 0,
    }
    summary_table = build_summary_table(summary)

    print("Writing outputs...")
    write_csv(out_dir / "jrc_france_commune_events_canonical.csv", jrc_df)
    write_csv(out_dir / "gaspar_commune_events_canonical.csv", gaspar_df)
    write_csv(out_dir / "commune_event_matches_window7.csv", commune_matches)
    write_csv(out_dir / "event_match_scores.csv", event_scores_ranked)
    write_csv(out_dir / "best_gaspar_match_per_jrc_event.csv", best_gaspar_per_jrc)
    write_csv(out_dir / "best_jrc_match_per_gaspar_event.csv", best_jrc_per_gaspar)
    write_csv(out_dir / "unmatched_jrc_commune_events.csv", unmatched_jrc)
    write_csv(out_dir / "unmatched_gaspar_commune_events.csv", unmatched_gaspar)
    write_csv(out_dir / "unmatched_jrc_events.csv", unmatched_jrc_events)
    write_csv(out_dir / "unmatched_gaspar_event_uids.csv", unmatched_gaspar_events)
    write_csv(out_dir / "comparison_summary.csv", summary_table)

    parquet_outputs = {
        "commune_event_matches_window7": maybe_write_parquet(out_dir / "commune_event_matches_window7.parquet", commune_matches),
        "event_match_scores": maybe_write_parquet(out_dir / "event_match_scores.parquet", event_scores_ranked),
    }

    excel_status = write_excel_workbook(
        out_dir / "jrc_gaspar_comparison.xlsx",
        [
            ("summary", summary_table),
            ("best_gaspar_per_jrc", best_gaspar_per_jrc),
            ("best_jrc_per_gaspar", best_jrc_per_gaspar),
            ("event_match_scores", event_scores_ranked),
            ("commune_matches", commune_matches),
            ("unmatched_jrc_events", unmatched_jrc_events),
            ("unmatched_gaspar_events", unmatched_gaspar_events),
        ],
    )

    diagnostics = {
        "summary": summary,
        "jrc_diagnostics": jrc_meta["diagnostics"],
        "gaspar_diagnostics": gaspar_meta["diagnostics"],
        "parquet_outputs": parquet_outputs,
        "excel_status": excel_status,
        "notes": {
            "gaspar_event_uid_definition": "cod_nat_catnat + dat_deb + dat_fin",
            "primary_match_rule": "same normalized INSEE commune code AND abs(start difference) <= window AND abs(end difference) <= window",
        },
    }
    (out_dir / "comparison_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Done.")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
