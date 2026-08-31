from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from france_commune_activity import (
    DEFAULT_FRANCE_LOOKUP_PATH,
    DEFAULT_GASPAR_FLOOD_RISK_LABELS,
    DEFAULT_GASPAR_FULL_HISTORY_DIR,
    DEFAULT_GASPAR_FULL_HISTORY_PROCESSED_PATH,
    DEFAULT_GASPAR_FULL_HISTORY_SHEET,
    DEFAULT_GASPAR_RAW_CSV_PATH,
    DEFAULT_OLD_INSEE_UPDATE_PATH,
    DEFAULT_GASPAR_SHEET,
    load_france_lookup,
    load_historical_insee_updates,
    prepare_raw_gaspar_rows,
    resolve_gaspar_current_communes,
)


DEFAULT_RESOLVED_CSV_PATH = DEFAULT_GASPAR_FULL_HISTORY_DIR / "gaspar_all_dates_resolved_current_communes.csv"
DEFAULT_DIAGNOSTICS_JSON_PATH = DEFAULT_GASPAR_FULL_HISTORY_DIR / "gaspar_all_dates_diagnostics.json"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a full-history France Gaspar flood workbook from raw catnat_gaspar.csv "
            "using only the flood-related risk labels and the existing commune-resolution logic."
        )
    )
    parser.add_argument(
        "--raw-gaspar-file",
        default=str(DEFAULT_GASPAR_RAW_CSV_PATH),
        help="Raw Gaspar source file. Default: data/raw/catnat_gaspar.csv",
    )
    parser.add_argument(
        "--france-lookup-file",
        default=str(DEFAULT_FRANCE_LOOKUP_PATH),
        help="France LAU to INSEE lookup CSV used to resolve current communes.",
    )
    parser.add_argument(
        "--france-old-insee-updates-file",
        default=str(DEFAULT_OLD_INSEE_UPDATE_PATH),
        help="Historical old-INSEE to current-INSEE CSV used for commune-code updates.",
    )
    parser.add_argument(
        "--out-file",
        default=str(DEFAULT_GASPAR_FULL_HISTORY_PROCESSED_PATH),
        help="Output Excel workbook for the cleaned full-history Gaspar rows.",
    )
    parser.add_argument(
        "--resolved-out-csv",
        default=str(DEFAULT_RESOLVED_CSV_PATH),
        help="Optional CSV with the same rows after current-commune resolution.",
    )
    parser.add_argument(
        "--diagnostics-json",
        default=str(DEFAULT_DIAGNOSTICS_JSON_PATH),
        help="JSON diagnostics output path.",
    )
    parser.add_argument(
        "--risk-label",
        action="append",
        default=None,
        help=(
            "Flood risk label to keep. Repeat to override the defaults. "
            "Default keeps the standard flood-related Gaspar labels."
        ),
    )
    return parser


def diagnostics_to_sheet_rows(diagnostics: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for section, values in diagnostics.items():
        if isinstance(values, dict):
            for key, value in values.items():
                rows.append({"section": section, "key": str(key), "value": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)})
        else:
            rows.append({"section": "summary", "key": str(section), "value": str(values)})
    return pd.DataFrame(rows, columns=["section", "key", "value"])


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    raw_gaspar_file = Path(args.raw_gaspar_file)
    france_lookup_file = Path(args.france_lookup_file)
    france_old_insee_updates_file = Path(args.france_old_insee_updates_file)
    out_file = Path(args.out_file)
    resolved_out_csv = Path(args.resolved_out_csv)
    diagnostics_json = Path(args.diagnostics_json)
    risk_labels = args.risk_label or DEFAULT_GASPAR_FLOOD_RISK_LABELS

    print("Loading and filtering raw Gaspar rows...")
    clean_df, clean_diagnostics = prepare_raw_gaspar_rows(
        raw_gaspar_file,
        flood_risk_labels=risk_labels,
    )

    print("Resolving Gaspar communes to current INSEE codes...")
    france_lookup = load_france_lookup(france_lookup_file)
    historical_updates = load_historical_insee_updates(france_old_insee_updates_file)
    resolved_df, resolved_diagnostics = resolve_gaspar_current_communes(
        clean_df,
        france_lookup=france_lookup,
        historical_updates=historical_updates,
    )

    summary = {
        "clean_diagnostics": clean_diagnostics,
        "resolved_diagnostics": resolved_diagnostics,
        "kept_risk_labels": risk_labels,
        "resolved_rows": int(resolved_df["gaspar_commune_match_found"].fillna(False).sum()),
        "unresolved_rows": int((~resolved_df["gaspar_commune_match_found"].fillna(False)).sum()),
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    resolved_out_csv.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_json.parent.mkdir(parents=True, exist_ok=True)

    print("Writing workbook and diagnostics...")
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        clean_df.to_excel(writer, sheet_name=DEFAULT_GASPAR_FULL_HISTORY_SHEET, index=False)
        if DEFAULT_GASPAR_SHEET != DEFAULT_GASPAR_FULL_HISTORY_SHEET:
            clean_df.to_excel(writer, sheet_name=DEFAULT_GASPAR_SHEET, index=False)
        resolved_df.to_excel(writer, sheet_name="GasparAllDatesResolved", index=False)
        diagnostics_to_sheet_rows(summary).to_excel(writer, sheet_name="Diagnostics", index=False)

    resolved_df.to_csv(resolved_out_csv, index=False, encoding="utf-8-sig")
    diagnostics_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Clean workbook: {out_file.resolve()}")
    print(f"Resolved CSV: {resolved_out_csv.resolve()}")
    print(f"Diagnostics JSON: {diagnostics_json.resolve()}")
    print(summary)


if __name__ == "__main__":
    main()
