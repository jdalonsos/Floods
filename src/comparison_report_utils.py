"""Helpers for concise comparison outputs and human-readable guides."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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
            f"## Detailed Audit Tables",
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
