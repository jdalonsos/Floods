from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Border, Font, PatternFill, Side


DEFAULT_SOURCE_WORKBOOK = Path("data/processed/T20_Anonymised.xlsx")
DEFAULT_JRC_WORKBOOK = Path("data/processed/T20_Anonymised_jrc_flood_check.xlsx")
DEFAULT_GASPAR_WORKBOOK = Path("data/processed/T20_Anonymised_gaspar_check.xlsx")
DEFAULT_OUTPUT_DIR = Path("outputs/flood_lgd_export")
DEFAULT_SHEET_NAME = "FLOOD_LGD"
DEFAULT_MODE = "copy"

OUTPUT_COLUMNS = [
    "Point ID",
    "Facility_ID",
    "CLOSED_DEFAULT_DATE",
    "ID_ADR",
    "TYPE_ADR",
    "FLAG_FLOOD_ADR",
    "FLAG_FLOOD_ADR_AREA",
    "DATE_REF_FLOOD",
    "DATE_END_FLOOD",
    "FLOOD_DEPTH_MAX",
    "FLOOD_DEPTH_MEDIAN",
    "FLOOD_DEPTH_MIN",
    "FLOOD_DURATION",
    "Flag_JRC",
    "Flag_GASPAR",
    "Flag_HANZE",
    "FLOOD_DATA_SOURCE",
]

COLUMN_WIDTHS = {
    "A": 13,
    "B": 16,
    "C": 22,
    "D": 28,
    "E": 14,
    "F": 18,
    "G": 22,
    "H": 18,
    "I": 18,
    "J": 18,
    "K": 20,
    "L": 18,
    "M": 16,
    "N": 13,
    "O": 15,
    "P": 15,
    "Q": 20,
}

HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)


@dataclass(frozen=True)
class FloodTarget:
    input_path: Path
    source_label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build FLOOD_LGD outputs from the checked JRC and Gaspar workbooks. "
            "Use --mode copy to append a new sheet into copied workbooks, "
            "--mode standalone to write only the FLOOD_LGD sheet as a small xlsx, "
            "or --mode csv for the fastest export."
        )
    )
    parser.add_argument("--source-workbook", default=str(DEFAULT_SOURCE_WORKBOOK), help="Original T20 workbook used to recover raw row fields such as Facility_ID.")
    parser.add_argument("--jrc-workbook", default=str(DEFAULT_JRC_WORKBOOK), help="JRC checked workbook containing an event_hits sheet.")
    parser.add_argument("--gaspar-workbook", default=str(DEFAULT_GASPAR_WORKBOOK), help="Gaspar checked workbook containing an event_hits sheet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Folder where the outputs will be written.")
    parser.add_argument("--sheet-name", default=DEFAULT_SHEET_NAME, help="Name of the derived sheet.")
    parser.add_argument(
        "--mode",
        default=DEFAULT_MODE,
        choices=["copy", "standalone", "csv"],
        help=(
            "copy: duplicate the original checked workbook and append the new sheet. "
            "standalone: create a small workbook containing only the FLOOD_LGD sheet. "
            "csv: export only the FLOOD_LGD data as csv."
        ),
    )
    parser.add_argument("--replace-sheet", action="store_true", help="In copy mode, replace the target sheet if it already exists in the copied workbook.")
    return parser.parse_args()


def ensure_required_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label}: {path}")


def parse_date(value: Any) -> datetime | None:
    if pd.isna(value) or value in ("", None):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.to_pydatetime()
    return parsed


def bool_to_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return 1
        if normalized in {"false", "no", "n", "0"}:
            return 0
    return None


def duration_days(start_value: Any, end_value: Any) -> int | None:
    start_date = parse_date(start_value)
    end_date = parse_date(end_value)
    if not start_date or not end_date:
        return None
    return (end_date.date() - start_date.date()).days


def coordinate_text(value: Any) -> str:
    if pd.isna(value) or value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.8f}"
    return str(value).strip()


def build_id_adr(record: pd.Series) -> str | None:
    latitude = coordinate_text(record.get("point_latitude"))
    longitude = coordinate_text(record.get("point_longitude"))
    if not latitude and not longitude:
        return None
    return f"{latitude}, {longitude}"


def load_source_rows(source_workbook: Path) -> dict[int, dict[str, Any]]:
    source_df = pd.read_excel(source_workbook).dropna(how="all").copy()
    source_df["point_id"] = range(1, len(source_df) + 1)
    return source_df.set_index("point_id").to_dict(orient="index")


def build_jrc_rows(event_hits: pd.DataFrame, source_rows: dict[int, dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for _, record in event_hits.iterrows():
        point_id = int(record["point_id"])
        source_row = source_rows.get(point_id, {})
        rows.append(
            [
                point_id,
                source_row.get("Facility_ID"),
                parse_date(record.get("study_period_end")),
                build_id_adr(record),
                None,
                bool_to_int(record.get("point_buffer_flood_hit")),
                bool_to_int(record.get("buffer_flood_hit")),
                parse_date(record.get("start_date")),
                parse_date(record.get("end_date")),
                record.get("buffer_max_depth_cm"),
                record.get("buffer_median_depth_cm"),
                record.get("buffer_min_depth_cm"),
                duration_days(record.get("start_date"), record.get("end_date")),
                1,
                None,
                None,
                "JRC",
            ]
        )
    return rows


def build_gaspar_rows(event_hits: pd.DataFrame, source_rows: dict[int, dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for _, record in event_hits.iterrows():
        point_id = int(record["point_id"])
        source_row = source_rows.get(point_id, {})
        rows.append(
            [
                point_id,
                source_row.get("Facility_ID"),
                parse_date(record.get("study_period_end")),
                build_id_adr(record),
                None,
                1,
                1,
                parse_date(record.get("gaspar_start_date")),
                parse_date(record.get("gaspar_end_date")),
                None,
                None,
                None,
                duration_days(record.get("gaspar_start_date"), record.get("gaspar_end_date")),
                None,
                1,
                None,
                "GASPAR",
            ]
        )
    return rows


def build_flood_lgd_rows(event_hits: pd.DataFrame, source_rows: dict[int, dict[str, Any]], source_label: str) -> list[list[Any]]:
    if source_label == "JRC":
        return build_jrc_rows(event_hits, source_rows)
    if source_label == "GASPAR":
        return build_gaspar_rows(event_hits, source_rows)
    raise ValueError(f"Unsupported source label: {source_label}")


def rows_to_dataframe(rows: list[list[Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def style_worksheet(worksheet) -> None:
    worksheet.freeze_panes = "A2"

    for cell in worksheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER

    worksheet.row_dimensions[1].height = 22

    for row in worksheet.iter_rows():
        for cell in row:
            cell.border = THIN_BORDER

    for column_letter, width in COLUMN_WIDTHS.items():
        worksheet.column_dimensions[column_letter].width = width

    max_row = worksheet.max_row
    if max_row < 2:
        return

    for column_letter in ("C", "H", "I"):
        for column_cells in worksheet[f"{column_letter}2:{column_letter}{max_row}"]:
            for cell in column_cells:
                cell.number_format = "yyyy-mm-dd"

    for column_letter in ("F", "G", "M", "N", "O", "P"):
        for column_cells in worksheet[f"{column_letter}2:{column_letter}{max_row}"]:
            for cell in column_cells:
                cell.number_format = "0"

    for column_letter in ("J", "K", "L"):
        for column_cells in worksheet[f"{column_letter}2:{column_letter}{max_row}"]:
            for cell in column_cells:
                cell.number_format = "0.##"


def write_sheet_into_existing_workbook(
    workbook_path: Path,
    output_path: Path,
    sheet_name: str,
    rows: list[list[Any]],
    *,
    replace_sheet: bool,
) -> None:
    workbook = load_workbook(workbook_path)

    if sheet_name in workbook.sheetnames:
        if not replace_sheet:
            raise ValueError(
                f"Sheet {sheet_name!r} already exists in {workbook_path.name}. "
                "Use --replace-sheet if you want to overwrite it in the copied workbook."
            )
        del workbook[sheet_name]

    worksheet = workbook.create_sheet(title=sheet_name)
    worksheet.append(OUTPUT_COLUMNS)
    for row in rows:
        worksheet.append(row)
    style_worksheet(worksheet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def write_standalone_workbook(
    output_path: Path,
    sheet_name: str,
    rows: list[list[Any]],
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet.append(OUTPUT_COLUMNS)
    for row in rows:
        worksheet.append(row)
    style_worksheet(worksheet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def write_csv_output(output_path: Path, rows: list[list[Any]]) -> None:
    df = rows_to_dataframe(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")


def build_output_path(input_path: Path, sheet_name: str, mode: str) -> Path:
    safe_sheet_name = sheet_name.replace(" ", "_")
    if mode == "copy":
        return Path(f"{input_path.stem}_with_{safe_sheet_name}{input_path.suffix}")
    if mode == "standalone":
        return Path(f"{input_path.stem}_{safe_sheet_name}_only.xlsx")
    if mode == "csv":
        return Path(f"{input_path.stem}_{safe_sheet_name}.csv")
    raise ValueError(f"Unsupported mode: {mode}")


def process_target(
    target: FloodTarget,
    *,
    output_dir: Path,
    sheet_name: str,
    source_rows: dict[int, dict[str, Any]],
    mode: str,
    replace_sheet: bool,
) -> Path:
    event_hits = pd.read_excel(target.input_path, sheet_name="event_hits")
    rows = build_flood_lgd_rows(event_hits, source_rows, target.source_label)
    output_path = output_dir / build_output_path(target.input_path, sheet_name, mode)

    if mode == "copy":
        write_sheet_into_existing_workbook(
            target.input_path,
            output_path,
            sheet_name,
            rows,
            replace_sheet=replace_sheet,
        )
    elif mode == "standalone":
        write_standalone_workbook(output_path, sheet_name, rows)
    elif mode == "csv":
        write_csv_output(output_path, rows)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    print(
        f"Wrote {output_path} with {len(rows)} {sheet_name} rows from "
        f"{target.source_label} using mode={mode}."
    )
    return output_path


def main() -> None:
    args = parse_args()

    source_workbook = Path(args.source_workbook)
    jrc_workbook = Path(args.jrc_workbook)
    gaspar_workbook = Path(args.gaspar_workbook)
    output_dir = Path(args.output_dir)

    ensure_required_file(source_workbook, "source workbook")
    ensure_required_file(jrc_workbook, "JRC workbook")
    ensure_required_file(gaspar_workbook, "Gaspar workbook")

    source_rows = load_source_rows(source_workbook)
    targets = [
        FloodTarget(input_path=jrc_workbook, source_label="JRC"),
        FloodTarget(input_path=gaspar_workbook, source_label="GASPAR"),
    ]

    for target in targets:
        process_target(
            target,
            output_dir=output_dir,
            sheet_name=args.sheet_name,
            source_rows=source_rows,
            mode=args.mode,
            replace_sheet=args.replace_sheet,
        )


if __name__ == "__main__":
    main()
