"""Create concise plots for France JRC vs Gaspar comparison outputs.

The script is designed for the flexible comparison output layout where:

- concise tables live at the top level of the comparison folder
- detailed audit tables live under ``details/``

It creates both row-level plots and event-level plots so partial event matches
are easier to interpret.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def read_tabular_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path, low_memory=False)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported tabular file format: {path}")


def resolve_preferred_path(
    comparison_dir: Path,
    stems: list[str],
    *,
    allow_details: bool,
) -> Path:
    search_dirs = [comparison_dir]
    if allow_details:
        search_dirs.append(comparison_dir / "details")

    for search_dir in search_dirs:
        for stem in stems:
            for suffix in [".csv", ".xlsx", ".xls"]:
                candidate = search_dir / f"{stem}{suffix}"
                if candidate.exists():
                    return candidate

    search_text = ", ".join(stems)
    detail_note = " or details/" if allow_details else ""
    raise FileNotFoundError(
        f"Could not find any of [{search_text}] in {comparison_dir}{detail_note}."
    )


def read_summary(comparison_dir: Path) -> dict[str, str]:
    summary_path = resolve_preferred_path(
        comparison_dir,
        ["comparison_summary"],
        allow_details=False,
    )
    summary_df = read_tabular_required(summary_path)
    if not {"metric", "value"}.issubset(summary_df.columns):
        raise KeyError(f"{summary_path} must contain 'metric' and 'value' columns.")
    return dict(zip(summary_df["metric"].astype(str), summary_df["value"].astype(str)))


def read_coverage_overview(comparison_dir: Path) -> pd.DataFrame:
    coverage_path = resolve_preferred_path(
        comparison_dir,
        ["coverage_overview"],
        allow_details=False,
    )
    coverage_df = read_tabular_required(coverage_path)
    required = {
        "level",
        "measurement",
        "jrc_matched",
        "jrc_total",
        "gaspar_matched",
        "gaspar_total",
    }
    missing = required - set(coverage_df.columns)
    if missing:
        raise KeyError(f"{coverage_path} is missing required columns: {sorted(missing)}")
    return coverage_df


def find_level_match_file(comparison_dir: Path, prefix: str) -> Path:
    search_dirs = [comparison_dir, comparison_dir / "details"]
    for search_dir in search_dirs:
        matches = sorted(search_dir.glob(f"{prefix}_flexible_*d.csv"))
        if not matches:
            continue
        if len(matches) > 1:
            raise FileExistsError(
                f"Multiple match files found for {prefix}: {[path.name for path in matches]}. "
                "Keep one file per comparison directory or move older runs away."
            )
        return matches[0]

    raise FileNotFoundError(
        f"No match file found in {comparison_dir} or {comparison_dir / 'details'} "
        f"for prefix '{prefix}_flexible_*d.csv'."
    )


def read_detail_table(comparison_dir: Path, stem: str) -> pd.DataFrame:
    path = resolve_preferred_path(comparison_dir, [stem], allow_details=True)
    return read_tabular_required(path)


def read_best_match_overview(comparison_dir: Path, level: str) -> pd.DataFrame:
    path = resolve_preferred_path(
        comparison_dir,
        [f"best_match_overview_{level}"],
        allow_details=False,
    )
    return read_tabular_required(path)


def to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def shorten_label(text: object, max_len: int = 40) -> str:
    label = str(text).strip()
    if len(label) <= max_len:
        return label
    return label[: max_len - 3] + "..."


def format_ratio_label(matched: float, total: float) -> str:
    share = matched / total if total else 0.0
    return f"{int(round(matched))}/{int(round(total))}\n{share:.0%}"


def build_source_coverage_rows(coverage_overview: pd.DataFrame, level: str, measurement: str) -> pd.DataFrame:
    subset = coverage_overview[
        coverage_overview["level"].astype(str).str.lower().eq(level.lower())
        & coverage_overview["measurement"].astype(str).str.lower().eq(measurement.lower())
    ]
    if subset.empty:
        return pd.DataFrame(columns=["source", "matched", "unmatched", "total"])

    row = subset.iloc[0]
    return pd.DataFrame(
        [
            {
                "source": "JRC",
                "matched": to_float(row["jrc_matched"]),
                "unmatched": max(to_float(row["jrc_total"]) - to_float(row["jrc_matched"]), 0.0),
                "total": to_float(row["jrc_total"]),
            },
            {
                "source": "Gaspar",
                "matched": to_float(row["gaspar_matched"]),
                "unmatched": max(
                    to_float(row["gaspar_total"]) - to_float(row["gaspar_matched"]),
                    0.0,
                ),
                "total": to_float(row["gaspar_total"]),
            },
        ]
    )


def plot_stacked_coverage(
    ax: plt.Axes,
    level_df: pd.DataFrame,
    title: str,
    ylabel: str,
) -> None:
    if level_df.empty:
        ax.text(0.5, 0.5, "No coverage data available", ha="center", va="center")
        ax.set_axis_off()
        return

    x = range(len(level_df))
    bars_matched = ax.bar(x, level_df["matched"], label="Matched", color="#2a9d8f")
    ax.bar(
        x,
        level_df["unmatched"],
        bottom=level_df["matched"],
        label="Unmatched",
        color="#d9d9d9",
    )
    ax.set_xticks(list(x), level_df["source"])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False)

    for idx, bar in enumerate(bars_matched):
        total = float(level_df.iloc[idx]["total"])
        matched = float(level_df.iloc[idx]["matched"])
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            total * 0.5 if total else 0.1,
            format_ratio_label(matched, total),
            ha="center",
            va="center",
            fontsize=9,
            color="#0f172a",
        )


def plot_overview(
    coverage_overview: pd.DataFrame,
    date_window_days: int,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    plot_stacked_coverage(
        axes[0, 0],
        build_source_coverage_rows(coverage_overview, "commune", "unique_events"),
        "Commune-Level Unique Event Coverage",
        "Unique event IDs",
    )
    plot_stacked_coverage(
        axes[0, 1],
        build_source_coverage_rows(coverage_overview, "department", "unique_events"),
        "Department-Level Unique Event Coverage",
        "Unique event IDs",
    )
    plot_stacked_coverage(
        axes[1, 0],
        build_source_coverage_rows(coverage_overview, "commune", "canonical_rows"),
        "Commune-Level Canonical Row Coverage",
        "Commune-event rows",
    )
    plot_stacked_coverage(
        axes[1, 1],
        build_source_coverage_rows(coverage_overview, "department", "canonical_rows"),
        "Department-Level Canonical Row Coverage",
        "Department-event rows",
    )

    fig.suptitle(
        f"JRC vs Gaspar Flexible Comparison Overview ({date_window_days}-day window)",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_reason_counts(ax: plt.Axes, matches: pd.DataFrame, level_label: str) -> None:
    if matches.empty or "flexible_match_reason" not in matches.columns:
        ax.text(0.5, 0.5, "No match reasons available", ha="center", va="center")
        ax.set_axis_off()
        return

    reason_counts = (
        matches["flexible_match_reason"]
        .fillna("missing")
        .astype(str)
        .value_counts()
        .sort_values(ascending=True)
    )
    ax.barh(reason_counts.index, reason_counts.values, color="#457b9d")
    ax.set_title(f"{level_label}: Match Reasons")
    ax.set_xlabel("Matched rows")


def plot_share_histogram(ax: plt.Axes, scores: pd.DataFrame, level_label: str) -> None:
    if scores.empty:
        ax.text(0.5, 0.5, "No event scores available", ha="center", va="center")
        ax.set_axis_off()
        return

    ax.hist(
        pd.to_numeric(scores["jrc_match_share"], errors="coerce").dropna(),
        bins=15,
        alpha=0.65,
        label="JRC match share",
        color="#1d3557",
    )
    ax.hist(
        pd.to_numeric(scores["gaspar_match_share"], errors="coerce").dropna(),
        bins=15,
        alpha=0.55,
        label="Gaspar match share",
        color="#e76f51",
    )
    ax.set_title(f"{level_label}: All Event-Pair Match Shares")
    ax.set_xlabel("Share")
    ax.set_ylabel("Event-pair count")
    ax.legend(frameon=False)


def plot_share_scatter(
    ax: plt.Axes,
    scores: pd.DataFrame,
    level_label: str,
    matched_col: str,
) -> None:
    if scores.empty:
        ax.text(0.5, 0.5, "No event scores available", ha="center", va="center")
        ax.set_axis_off()
        return

    ranked = scores.copy()
    reciprocal = ranked.get("reciprocal_best_match", pd.Series(False, index=ranked.index))
    reciprocal = reciprocal.fillna(False).astype(bool)

    x_other = pd.to_numeric(ranked.loc[~reciprocal, "jrc_match_share"], errors="coerce")
    y_other = pd.to_numeric(ranked.loc[~reciprocal, "gaspar_match_share"], errors="coerce")
    size_other = 20 + pd.to_numeric(
        ranked.loc[~reciprocal, matched_col],
        errors="coerce",
    ).fillna(0) * 3
    ax.scatter(
        x_other,
        y_other,
        s=size_other,
        alpha=0.5,
        color="#bdbdbd",
        label="Other pairs",
    )

    x_best = pd.to_numeric(ranked.loc[reciprocal, "jrc_match_share"], errors="coerce")
    y_best = pd.to_numeric(ranked.loc[reciprocal, "gaspar_match_share"], errors="coerce")
    size_best = 28 + pd.to_numeric(
        ranked.loc[reciprocal, matched_col],
        errors="coerce",
    ).fillna(0) * 4
    ax.scatter(
        x_best,
        y_best,
        s=size_best,
        alpha=0.85,
        color="#2a9d8f",
        label="Reciprocal best",
    )
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("JRC match share")
    ax.set_ylabel("Gaspar match share")
    ax.set_title(f"{level_label}: All Candidate Event Pairs")
    ax.legend(frameon=False, loc="lower right")


def plot_top_units(
    ax: plt.Axes,
    matches: pd.DataFrame,
    unit_col: str,
    title: str,
) -> None:
    if matches.empty or unit_col not in matches.columns:
        ax.text(0.5, 0.5, "No unit-level matches available", ha="center", va="center")
        ax.set_axis_off()
        return

    counts = matches[unit_col].dropna().astype(str).value_counts().head(12).sort_values()
    if counts.empty:
        ax.text(0.5, 0.5, "No unit-level matches available", ha="center", va="center")
        ax.set_axis_off()
        return

    ax.barh(counts.index, counts.values, color="#8d99ae")
    ax.set_title(title)
    ax.set_xlabel("Matched rows")


def plot_level_summary(
    matches: pd.DataFrame,
    scores: pd.DataFrame,
    level_label: str,
    matched_col: str,
    unit_col: str,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    plot_reason_counts(axes[0, 0], matches, level_label)
    plot_share_histogram(axes[0, 1], scores, level_label)
    plot_share_scatter(axes[1, 0], scores, level_label, matched_col)
    plot_top_units(axes[1, 1], matches, unit_col, f"{level_label}: Top {unit_col} by matched rows")

    fig.suptitle(f"{level_label}-Level Row and Candidate-Pair Summary", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def classify_event_overlap(jrc_share: float, gaspar_share: float) -> str:
    if jrc_share >= 0.999 and gaspar_share >= 0.999:
        return "Full overlap both sides"
    if jrc_share >= 0.999:
        return "JRC full, Gaspar partial"
    if gaspar_share >= 0.999:
        return "Gaspar full, JRC partial"
    if min(jrc_share, gaspar_share) >= 0.75:
        return "Strong partial overlap"
    if min(jrc_share, gaspar_share) >= 0.50:
        return "Moderate partial overlap"
    return "Weak partial overlap"


def build_event_plot_table(
    best_matches: pd.DataFrame,
    matched_col: str,
    exact_col: str,
) -> pd.DataFrame:
    if best_matches.empty:
        return best_matches.copy()

    event_df = best_matches.copy()
    event_df["jrc_match_share"] = pd.to_numeric(
        event_df["jrc_match_share"],
        errors="coerce",
    ).fillna(0.0)
    event_df["gaspar_match_share"] = pd.to_numeric(
        event_df["gaspar_match_share"],
        errors="coerce",
    ).fillna(0.0)
    event_df[matched_col] = pd.to_numeric(event_df[matched_col], errors="coerce").fillna(0.0)
    if exact_col in event_df.columns:
        event_df[exact_col] = pd.to_numeric(event_df[exact_col], errors="coerce").fillna(0.0)
    else:
        event_df[exact_col] = 0.0

    event_df["combined_match_share"] = (
        event_df["jrc_match_share"] + event_df["gaspar_match_share"]
    ) / 2.0
    event_df["exact_unit_share"] = 0.0
    matched_positive = event_df[matched_col] > 0
    event_df.loc[matched_positive, "exact_unit_share"] = (
        event_df.loc[matched_positive, exact_col] / event_df.loc[matched_positive, matched_col]
    )
    if "reciprocal_best_match" in event_df.columns:
        event_df["reciprocal_best_match"] = (
            event_df["reciprocal_best_match"].fillna(False).astype(bool)
        )
    else:
        event_df["reciprocal_best_match"] = False
    event_df["event_overlap_class"] = event_df.apply(
        lambda row: classify_event_overlap(
            float(row["jrc_match_share"]),
            float(row["gaspar_match_share"]),
        ),
        axis=1,
    )

    if "cod_nat_catnat" in event_df.columns:
        pair_target = event_df["cod_nat_catnat"].fillna(event_df.get("gaspar_event_uid", ""))
    elif "gaspar_event_uid" in event_df.columns:
        pair_target = event_df["gaspar_event_uid"]
    else:
        pair_target = pd.Series("", index=event_df.index)
    event_df["event_pair_label"] = [
        shorten_label(f"{left} -> {right}", max_len=46)
        for left, right in zip(
            event_df["jrc_event_id"].astype(str),
            pair_target.astype(str),
        )
    ]
    return event_df


def plot_event_overlap_classes(ax: plt.Axes, event_df: pd.DataFrame, level_label: str) -> None:
    if event_df.empty:
        ax.text(0.5, 0.5, "No best-match events available", ha="center", va="center")
        ax.set_axis_off()
        return

    class_order = [
        "Weak partial overlap",
        "Moderate partial overlap",
        "Strong partial overlap",
        "Gaspar full, JRC partial",
        "JRC full, Gaspar partial",
        "Full overlap both sides",
    ]
    counts = (
        event_df["event_overlap_class"]
        .astype(str)
        .value_counts()
        .reindex(class_order, fill_value=0)
    )
    counts = counts[counts > 0]
    ax.barh(counts.index, counts.values, color="#6c8ebf")
    ax.set_title(f"{level_label}: Best Event-Pair Overlap Classes")
    ax.set_xlabel("Best-match event pairs")


def plot_best_event_scatter(
    ax: plt.Axes,
    event_df: pd.DataFrame,
    level_label: str,
    matched_col: str,
) -> None:
    if event_df.empty:
        ax.text(0.5, 0.5, "No best-match events available", ha="center", va="center")
        ax.set_axis_off()
        return

    reciprocal = event_df["reciprocal_best_match"]
    x_other = event_df.loc[~reciprocal, "jrc_match_share"]
    y_other = event_df.loc[~reciprocal, "gaspar_match_share"]
    x_best = event_df.loc[reciprocal, "jrc_match_share"]
    y_best = event_df.loc[reciprocal, "gaspar_match_share"]

    ax.scatter(
        x_other,
        y_other,
        s=32 + event_df.loc[~reciprocal, matched_col] * 6,
        alpha=0.55,
        color="#bdbdbd",
        label="Best for JRC only",
    )
    ax.scatter(
        x_best,
        y_best,
        s=40 + event_df.loc[reciprocal, matched_col] * 7,
        alpha=0.9,
        color="#2a9d8f",
        label="Reciprocal best",
    )
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("JRC event share")
    ax.set_ylabel("Gaspar event share")
    ax.set_title(f"{level_label}: Best Event-Pair Shares")
    ax.legend(frameon=False, loc="lower right")


def plot_event_date_differences(ax: plt.Axes, event_df: pd.DataFrame, level_label: str) -> None:
    if event_df.empty:
        ax.text(0.5, 0.5, "No best-match events available", ha="center", va="center")
        ax.set_axis_off()
        return

    min_diff = pd.to_numeric(event_df["min_total_abs_date_diff_days"], errors="coerce").dropna()
    mean_diff = pd.to_numeric(event_df["mean_total_abs_date_diff_days"], errors="coerce").dropna()
    if min_diff.empty and mean_diff.empty:
        ax.text(0.5, 0.5, "No event date-difference values", ha="center", va="center")
        ax.set_axis_off()
        return

    bins = 15
    if not min_diff.empty:
        ax.hist(min_diff, bins=bins, alpha=0.65, label="Min total abs diff", color="#264653")
    if not mean_diff.empty:
        ax.hist(mean_diff, bins=bins, alpha=0.55, label="Mean total abs diff", color="#f4a261")
    ax.set_title(f"{level_label}: Best Event-Pair Date Differences")
    ax.set_xlabel("Days")
    ax.set_ylabel("Best-match event pairs")
    ax.legend(frameon=False)


def plot_top_event_pairs(
    ax: plt.Axes,
    event_df: pd.DataFrame,
    level_label: str,
    matched_col: str,
    top_n: int,
) -> None:
    if event_df.empty:
        ax.text(0.5, 0.5, "No best-match events available", ha="center", va="center")
        ax.set_axis_off()
        return

    ranked = event_df.sort_values(
        by=[
            "reciprocal_best_match",
            "combined_match_share",
            matched_col,
            "min_total_abs_date_diff_days",
        ],
        ascending=[False, False, False, True],
        kind="stable",
    ).head(top_n)
    if ranked.empty:
        ax.text(0.5, 0.5, "No best-match events available", ha="center", va="center")
        ax.set_axis_off()
        return

    labels = ranked["event_pair_label"].tolist()[::-1]
    values = ranked["combined_match_share"].tolist()[::-1]
    colors = ["#2a9d8f" if flag else "#8d99ae" for flag in ranked["reciprocal_best_match"]][::-1]
    ax.barh(labels, values, color=colors)
    ax.set_xlim(0.0, 1.02)
    ax.set_xlabel("Average of JRC and Gaspar event shares")
    ax.set_title(f"{level_label}: Top Best-Match Event Pairs")


def plot_event_summary(
    best_matches: pd.DataFrame,
    level_label: str,
    matched_col: str,
    exact_col: str,
    top_n: int,
    out_path: Path,
) -> None:
    event_df = build_event_plot_table(best_matches, matched_col=matched_col, exact_col=exact_col)

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    plot_event_overlap_classes(axes[0, 0], event_df, level_label)
    plot_best_event_scatter(axes[0, 1], event_df, level_label, matched_col)
    plot_event_date_differences(axes[1, 0], event_df, level_label)
    plot_top_event_pairs(axes[1, 1], event_df, level_label, matched_col, top_n=top_n)

    fig.suptitle(
        f"{level_label}-Level Best Event-Match Summary (best Gaspar per JRC event)",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create row-level and event-level summary plots from "
            "compare_france_jrc_gaspar_flexible.py outputs."
        )
    )
    parser.add_argument(
        "--comparison-dir",
        default="data/processed/jrc_gaspar_comparison_flexible_7d",
        help=(
            "Directory containing the flexible comparison outputs. "
            "Default: data/processed/jrc_gaspar_comparison_flexible_7d"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Directory where PNG plots should be written. "
            "Default: <comparison-dir>/plots"
        ),
    )
    parser.add_argument(
        "--top-n-events",
        type=int,
        default=12,
        help="Number of top best-match event pairs to show in event plots. Default: 12.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    comparison_dir = Path(args.comparison_dir)
    out_dir = Path(args.out_dir) if args.out_dir else comparison_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = read_summary(comparison_dir)
    coverage_overview = read_coverage_overview(comparison_dir)
    commune_best_matches = read_best_match_overview(comparison_dir, "commune")
    department_best_matches = read_best_match_overview(comparison_dir, "department")

    commune_matches = read_tabular_required(find_level_match_file(comparison_dir, "commune_event_matches"))
    department_matches = read_tabular_required(
        find_level_match_file(comparison_dir, "department_event_matches")
    )
    commune_scores = read_detail_table(comparison_dir, "commune_event_match_scores")
    department_scores = read_detail_table(comparison_dir, "department_event_match_scores")

    overview_path = out_dir / "comparison_overview.png"
    commune_path = out_dir / "commune_level_summary.png"
    department_path = out_dir / "department_level_summary.png"
    commune_event_path = out_dir / "commune_event_summary.png"
    department_event_path = out_dir / "department_event_summary.png"

    plot_overview(
        coverage_overview=coverage_overview,
        date_window_days=int(float(summary.get("date_window_days", 0) or 0)),
        out_path=overview_path,
    )
    plot_level_summary(
        matches=commune_matches,
        scores=commune_scores,
        level_label="Commune",
        matched_col="matched_communes",
        unit_col="insee_com",
        out_path=commune_path,
    )
    plot_level_summary(
        matches=department_matches,
        scores=department_scores,
        level_label="Department",
        matched_col="matched_departments",
        unit_col="department_code",
        out_path=department_path,
    )
    plot_event_summary(
        best_matches=commune_best_matches,
        level_label="Commune",
        matched_col="matched_communes",
        exact_col="exact_date_commune_matches",
        top_n=args.top_n_events,
        out_path=commune_event_path,
    )
    plot_event_summary(
        best_matches=department_best_matches,
        level_label="Department",
        matched_col="matched_departments",
        exact_col="exact_date_department_matches",
        top_n=args.top_n_events,
        out_path=department_event_path,
    )

    manifest = {
        "comparison_dir": str(comparison_dir),
        "plots": {
            "overview": str(overview_path),
            "commune_level": str(commune_path),
            "department_level": str(department_path),
            "commune_events": str(commune_event_path),
            "department_events": str(department_event_path),
        },
        "plot_basis": {
            "overview": "coverage_overview top-level table",
            "row_level": "detailed match rows and detailed event score tables",
            "event_level": "best_match_overview top-level tables (best Gaspar per JRC event)",
        },
    }
    (out_dir / "plot_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
