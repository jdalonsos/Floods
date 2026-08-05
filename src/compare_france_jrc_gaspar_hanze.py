"""Compare French flood events from JRC, GASPAR and HANZE at NUTS3 level.

The three sources do not share commune-level geometry, so NUTS3 is the finest
common comparison unit.  Events match when they share a NUTS3 code and their
date intervals overlap after expansion by a configurable number of days.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from compare_france_jrc_gaspar_flexible import (
    build_department_reference_from_lookup,
    prepare_gaspar_commune_events_flexible,
    prepare_jrc_commune_events_flexible,
)


DEFAULT_JRC = Path("data/processed/france_lau_insee_documentation/events_fr_insee_long.csv")
DEFAULT_GASPAR = Path("data/processed/Gaspar_2015_2024.xlsx")
DEFAULT_HANZE = Path("data/processed/HANZE_events_v3_transformed.csv")
DEFAULT_LOOKUP = Path("data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv")
DEFAULT_OUT = Path("data/processed/jrc_gaspar_hanze_comparison_30d")


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA})


def parse_hanze_dates(series: pd.Series) -> pd.Series:
    """Parse the ISO and DD/MM/YYYY values found together in HANZE exports."""
    text = normalize_text(series)
    parsed = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")
    iso = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)
    slash = text.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", na=False)
    parsed.loc[iso] = pd.to_datetime(text.loc[iso], format="%Y-%m-%d", errors="coerce")
    parsed.loc[slash] = pd.to_datetime(text.loc[slash], format="%d/%m/%Y", errors="coerce")
    other = text.notna() & ~(iso | slash)
    parsed.loc[other] = pd.to_datetime(text.loc[other], errors="coerce", dayfirst=True)
    return parsed.dt.normalize()


def aggregate_jrc(jrc_communes: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    df = jrc_communes.copy()
    df["nuts3_code"] = normalize_text(df["nuts3_code"])
    df = df.loc[
        df["nuts3_code"].notna()
        & df["jrc_end_date"].ge(start)
        & df["jrc_start_date"].le(end)
    ].copy()
    aggregations: dict[str, tuple[str, object]] = {
        "nuts3_name": ("nuts3_name", "first"),
        "communes": ("insee_com", "nunique"),
    }
    if "max_depth_cm" in df.columns:
        aggregations["max_depth_cm"] = ("max_depth_cm", "max")
    if "flooded_area_m2" in df.columns:
        aggregations["flooded_area_m2"] = ("flooded_area_m2", "sum")
    result = (
        df.groupby(
            ["jrc_event_id", "nuts3_code", "jrc_start_date", "jrc_end_date"],
            dropna=False,
        )
        .agg(**aggregations)
        .reset_index()
        .rename(
            columns={
                "jrc_event_id": "event_id",
                "jrc_start_date": "start_date",
                "jrc_end_date": "end_date",
            }
        )
    )
    result["event_id"] = normalize_text(result["event_id"])
    return result.sort_values(["event_id", "nuts3_code"]).reset_index(drop=True)


def aggregate_gaspar(
    gaspar_communes: pd.DataFrame,
    department_reference: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    reference = department_reference[
        ["department_code", "dept_ref_nuts3_code", "dept_ref_nuts3_name"]
    ].copy()
    df = gaspar_communes.merge(reference, on="department_code", how="left", validate="m:1")
    df["nuts3_code"] = normalize_text(df["dept_ref_nuts3_code"])
    df = df.loc[
        df["nuts3_code"].notna()
        & df["gaspar_end_date"].ge(start)
        & df["gaspar_start_date"].le(end)
    ].copy()
    result = (
        df.groupby(
            [
                "gaspar_event_uid",
                "cod_nat_catnat",
                "nuts3_code",
                "gaspar_start_date",
                "gaspar_end_date",
            ],
            dropna=False,
        )
        .agg(
            nuts3_name=("dept_ref_nuts3_name", "first"),
            communes=("insee_com", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "gaspar_event_uid": "event_id",
                "gaspar_start_date": "start_date",
                "gaspar_end_date": "end_date",
            }
        )
    )
    result["event_id"] = normalize_text(result["event_id"])
    return result.sort_values(["event_id", "nuts3_code"]).reset_index(drop=True)


def aggregate_hanze(path: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    raw = pd.read_csv(path, low_memory=False)
    required = {"ID", "Country code", "Start date", "End date", "Type", "NUTS3"}
    missing = required - set(raw.columns)
    if missing:
        raise KeyError(f"HANZE input is missing required columns: {sorted(missing)}")
    df = raw.loc[normalize_text(raw["Country code"]).eq("FR")].copy()
    df["start_date"] = parse_hanze_dates(df["Start date"])
    df["end_date"] = parse_hanze_dates(df["End date"])
    df["start_date"] = df["start_date"].combine_first(df["end_date"])
    df["end_date"] = df["end_date"].combine_first(df["start_date"])
    df["nuts3_code"] = normalize_text(df["NUTS3"])
    df["event_id"] = normalize_text(df["ID"])
    df = df.loc[
        df["event_id"].notna()
        & df["nuts3_code"].notna()
        & df["start_date"].notna()
        & df["end_date"].notna()
        & df["end_date"].ge(start)
        & df["start_date"].le(end)
    ].copy()
    name_col = "NUTS3_name" if "NUTS3_name" in df.columns else "NUTS3"
    source_col = "Flood source" if "Flood source" in df.columns else "Type"
    result = (
        df.groupby(["event_id", "nuts3_code", "start_date", "end_date"], dropna=False)
        .agg(
            nuts3_name=(name_col, "first"),
            event_type=("Type", "first"),
            flood_source=(source_col, "first"),
        )
        .reset_index()
    )
    return result.sort_values(["event_id", "nuts3_code"]).reset_index(drop=True)


def interval_match(left: pd.DataFrame, right: pd.DataFrame, left_name: str, right_name: str, window: int) -> pd.DataFrame:
    left_prefixed = left.rename(
        columns={column: f"{left_name}_{column}" for column in left.columns if column != "nuts3_code"}
    )
    right_prefixed = right.rename(
        columns={column: f"{right_name}_{column}" for column in right.columns if column != "nuts3_code"}
    )
    merged = left_prefixed.merge(right_prefixed, on="nuts3_code", how="inner", validate="m:m")
    if merged.empty:
        return merged
    left_start = merged[f"{left_name}_start_date"]
    left_end = merged[f"{left_name}_end_date"]
    right_start = merged[f"{right_name}_start_date"]
    right_end = merged[f"{right_name}_end_date"]
    merged["gap_days"] = (pd.concat([left_start, right_start], axis=1).max(axis=1) - pd.concat([left_end, right_end], axis=1).min(axis=1)).dt.days.clip(lower=0)
    merged["interval_overlap_days"] = (
        pd.concat([left_end, right_end], axis=1).min(axis=1)
        - pd.concat([left_start, right_start], axis=1).max(axis=1)
    ).dt.days.add(1).clip(lower=0)
    merged["start_diff_days"] = (left_start - right_start).dt.days
    merged["end_diff_days"] = (left_end - right_end).dt.days
    merged["date_window_days"] = window
    matched = merged.loc[
        left_start.le(right_end + pd.Timedelta(days=window))
        & right_start.le(left_end + pd.Timedelta(days=window))
    ].copy()
    return matched.sort_values(
        [f"{left_name}_event_id", f"{right_name}_event_id", "nuts3_code", "gap_days"],
        kind="stable",
    ).reset_index(drop=True)


def event_coverage(source: pd.DataFrame, matches: pd.DataFrame, event_column: str) -> tuple[int, int, float]:
    total = int(source["event_id"].nunique())
    matched = int(matches[event_column].nunique()) if not matches.empty else 0
    return total, matched, matched / total if total else 0.0


def build_triple_matches(jg: pd.DataFrame, jh: pd.DataFrame, gh: pd.DataFrame) -> pd.DataFrame:
    if jg.empty or jh.empty or gh.empty:
        return pd.DataFrame()
    triples = jg.merge(
        jh,
        on=["jrc_event_id", "nuts3_code"],
        how="inner",
        suffixes=("_jg", "_jh"),
    )
    keep = gh[["gaspar_event_id", "hanze_event_id", "nuts3_code"]].drop_duplicates()
    triples = triples.merge(
        keep,
        on=["gaspar_event_id", "hanze_event_id", "nuts3_code"],
        how="inner",
        validate="m:1",
    )
    key = ["jrc_event_id", "gaspar_event_id", "hanze_event_id", "nuts3_code"]
    return triples.sort_values(key, kind="stable").drop_duplicates(key).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Three-source France flood comparison at NUTS3 level.")
    parser.add_argument("--jrc-file", default=str(DEFAULT_JRC))
    parser.add_argument("--gaspar-file", default=str(DEFAULT_GASPAR))
    parser.add_argument("--gaspar-sheet", default="Gaspar20152024FloodsClean")
    parser.add_argument("--hanze-file", default=str(DEFAULT_HANZE))
    parser.add_argument("--france-lookup-file", default=str(DEFAULT_LOOKUP))
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--date-window-days", type=int, default=30)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = pd.Timestamp(args.start_date).normalize()
    end = pd.Timestamp(args.end_date).normalize()
    if start > end:
        raise ValueError("start-date must be on or before end-date")
    if args.date_window_days < 0:
        raise ValueError("date-window-days must be non-negative")

    out = Path(args.out_dir)
    details = out / "details"
    details.mkdir(parents=True, exist_ok=True)

    jrc_communes, jrc_meta = prepare_jrc_commune_events_flexible(args.jrc_file)
    gaspar_communes, gaspar_meta = prepare_gaspar_commune_events_flexible(args.gaspar_file, args.gaspar_sheet)
    department_reference, reference_meta = build_department_reference_from_lookup(args.france_lookup_file)

    jrc = aggregate_jrc(jrc_communes, start, end)
    gaspar = aggregate_gaspar(gaspar_communes, department_reference, start, end)
    hanze = aggregate_hanze(Path(args.hanze_file), start, end)

    jg = interval_match(jrc, gaspar, "jrc", "gaspar", args.date_window_days)
    jh = interval_match(jrc, hanze, "jrc", "hanze", args.date_window_days)
    gh = interval_match(gaspar, hanze, "gaspar", "hanze", args.date_window_days)
    triples = build_triple_matches(jg, jh, gh)

    rows = []
    for left_name, right_name, left, right, matches in (
        ("jrc", "gaspar", jrc, gaspar, jg),
        ("jrc", "hanze", jrc, hanze, jh),
        ("gaspar", "hanze", gaspar, hanze, gh),
    ):
        left_total, left_matched, left_share = event_coverage(left, matches, f"{left_name}_event_id")
        right_total, right_matched, right_share = event_coverage(right, matches, f"{right_name}_event_id")
        rows.append(
            {
                "comparison": f"{left_name.upper()} vs {right_name.upper()}",
                "left_source": left_name.upper(),
                "left_total_events": left_total,
                "left_matched_events": left_matched,
                "left_match_share": left_share,
                "right_source": right_name.upper(),
                "right_total_events": right_total,
                "right_matched_events": right_matched,
                "right_match_share": right_share,
                "matched_event_pairs": int(matches[[f"{left_name}_event_id", f"{right_name}_event_id"]].drop_duplicates().shape[0]) if not matches.empty else 0,
                "matched_nuts3_rows": int(len(matches)),
            }
        )
    pairwise_summary = pd.DataFrame(rows)
    triple_summary = pd.DataFrame(
        [
            {
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
                "date_window_days": args.date_window_days,
                "jrc_total_events": int(jrc["event_id"].nunique()),
                "gaspar_total_events": int(gaspar["event_id"].nunique()),
                "hanze_total_events": int(hanze["event_id"].nunique()),
                "triple_event_combinations": int(
                    triples[["jrc_event_id", "gaspar_event_id", "hanze_event_id"]].drop_duplicates().shape[0]
                ) if not triples.empty else 0,
                "jrc_events_in_triple_matches": int(triples["jrc_event_id"].nunique()) if not triples.empty else 0,
                "gaspar_events_in_triple_matches": int(triples["gaspar_event_id"].nunique()) if not triples.empty else 0,
                "hanze_events_in_triple_matches": int(triples["hanze_event_id"].nunique()) if not triples.empty else 0,
                "triple_nuts3_rows": int(len(triples)),
            }
        ]
    )

    for name, frame in (
        ("jrc_nuts3_events", jrc),
        ("gaspar_nuts3_events", gaspar),
        ("hanze_nuts3_events", hanze),
        ("jrc_gaspar_matches", jg),
        ("jrc_hanze_matches", jh),
        ("gaspar_hanze_matches", gh),
        ("three_source_matches", triples),
    ):
        frame.to_csv(details / f"{name}.csv", index=False, encoding="utf-8-sig")
    pairwise_summary.to_csv(out / "pairwise_summary.csv", index=False, encoding="utf-8-sig")
    triple_summary.to_csv(out / "three_source_summary.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(out / "jrc_gaspar_hanze_comparison.xlsx", engine="openpyxl") as writer:
        pairwise_summary.to_excel(writer, sheet_name="pairwise_summary", index=False)
        triple_summary.to_excel(writer, sheet_name="three_source_summary", index=False)
        triples.to_excel(writer, sheet_name="three_source_matches", index=False)

    diagnostics = {
        "parameters": {
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "date_window_days": args.date_window_days,
            "common_spatial_level": "NUTS3",
        },
        "source_preparation": {
            "jrc": jrc_meta["diagnostics"],
            "gaspar": gaspar_meta["diagnostics"],
            "department_reference": reference_meta,
        },
        "matching_rule": "same NUTS3 and date intervals overlap after expansion by date_window_days",
        "interpretation": "Matches indicate event compatibility at NUTS3 level, not proof that identical physical footprints were observed.",
    }
    (details / "comparison_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(pairwise_summary.to_string(index=False))
    print(triple_summary.to_string(index=False))
    print(f"Outputs written to {out.resolve()}")


if __name__ == "__main__":
    main()
