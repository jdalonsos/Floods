from pathlib import Path

import pandas as pd


def show_workbook(path: str) -> None:
    book = pd.ExcelFile(path)
    print(f"\nFILE {path}: {book.sheet_names}")
    for sheet in book.sheet_names[:2]:
        frame = pd.read_excel(path, sheet_name=sheet)
        print(sheet, frame.shape, list(frame.columns))
        print(frame.head(2).to_string(index=False))


if __name__ == "__main__":
    RUN_LEGACY_WORKBOOK_INSPECTION = False
    if RUN_LEGACY_WORKBOOK_INSPECTION:
        for workbook in (
            "data/gaspar_floods.xlsx",
            "data/processed/Gaspar_2015_2024.xlsx",
        ):
            show_workbook(workbook)
    '''
    for workbook in (
        "data/gaspar_floods.xlsx",
        "data/processed/Gaspar_2015_2024.xlsx",
    ):
        show_workbook(workbook)

    gaspar = pd.read_excel("data/gaspar_floods.xlsx")
    gaspar["start"] = pd.to_datetime(gaspar["dat_deb"], errors="coerce")
    gaspar["end"] = pd.to_datetime(gaspar["dat_fin"], errors="coerce")
    gaspar = gaspar.loc[
        gaspar["start"].between("2005-01-01", "2024-12-31")
        & gaspar["end"].between("2005-01-01", "2024-12-31")
    ].copy()
    gaspar["duration_days"] = (gaspar["end"] - gaspar["start"]).dt.days
    print("\nTOP GASPAR ROWS")
    print(
        gaspar.sort_values("duration_days", ascending=False)[
            ["cod_nat_catnat", "cod_commune", "lib_commune", "lib_risque_jo", "start", "end", "duration_days"]
        ].head(20).to_string(index=False)
    )
    '''

    columns = [
        "row_id", "insee", "commune", "epci_code", "epci_name", "department_code",
        "department", "region_code", "region", "petr_code", "petr_name", "pnr",
        "hazard", "start", "end", "order_date",
    ]
    latest = pd.read_csv(
        "data/processed/catnat_latest_20260720.csv", sep=";", names=columns,
        header=None, encoding="utf-8", low_memory=False,
    )
    latest["start"] = pd.to_datetime(latest["start"], errors="coerce")
    latest["end"] = pd.to_datetime(latest["end"], errors="coerce")
    latest = latest.loc[
        latest["hazard"].str.contains("Inond", case=False, na=False)
        & latest["start"].between("2005-01-01", "2024-12-31")
        & latest["end"].between("2005-01-01", "2024-12-31")
    ].copy()
    latest["duration_days"] = (latest["end"] - latest["start"]).dt.days
    print("\nTOP CURRENT CATNAT/GASPAR-DERIVED ROWS")
    print(latest.sort_values("duration_days", ascending=False).head(30).to_string(index=False))
