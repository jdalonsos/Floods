"""
Expand HANZE events so each NUTS3 region in ``Regions affected (v2024)`` gets
its own row, enriched with the official NUTS3 name from the Eurostat
GeoPackage.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


REGIONS_COLUMN = "Regions affected (v2024)"
DEFAULT_INPUT = Path("data/raw/HANZE_events_v3.csv")
DEFAULT_NUTS = Path("data/raw/NUTS_RG_01M_2024_4326.gpkg")
DEFAULT_OUTPUT = Path("data/processed/HANZE_events_v3_transformed.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Expand HANZE rows by NUTS3 code from the "
            f"'{REGIONS_COLUMN}' column and attach official NUTS names."
        )
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to HANZE_events_v3.csv.",
    )
    parser.add_argument(
        "--nuts",
        default=str(DEFAULT_NUTS),
        help="Path to the official Eurostat NUTS GeoPackage.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to the transformed output CSV.",
    )
    return parser.parse_args()


def read_hanze_csv(path: str | Path) -> pd.DataFrame:
    encodings = ("cp1252", "latin1", "utf-8-sig", "utf-8")
    last_error: UnicodeDecodeError | None = None

    for encoding in encodings:
        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                low_memory=False,
                encoding=encoding,
            )
            df.columns = [str(column).strip() for column in df.columns]
            break
        except UnicodeDecodeError as error:
            last_error = error
    else:
        raise ValueError(f"Could not decode HANZE CSV at {path}.") from last_error

    if REGIONS_COLUMN not in df.columns:
        raise KeyError(
            f"Missing required HANZE column '{REGIONS_COLUMN}' in {path}."
        )

    return df


def get_feature_table_name(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        """
        SELECT table_name
        FROM gpkg_contents
        WHERE data_type = 'features'
        ORDER BY table_name
        LIMIT 1
        """
    ).fetchone()
    if row is None or not row[0]:
        raise ValueError("Could not find a feature table inside the NUTS GeoPackage.")
    return str(row[0])


def load_nuts3_lookup(path: str | Path) -> pd.DataFrame:
    connection = sqlite3.connect(path)
    try:
        table_name = get_feature_table_name(connection)
        query = (
            "SELECT NUTS_ID, NUTS_NAME, LEVL_CODE, CNTR_CODE "
            f"FROM [{table_name}] "
            "WHERE LEVL_CODE = 3"
        )
        lookup = pd.read_sql_query(query, connection)
    finally:
        connection.close()

    required_columns = {"NUTS_ID", "NUTS_NAME", "CNTR_CODE"}
    if not required_columns.issubset(lookup.columns):
        raise KeyError(
            "Unsupported NUTS schema. Expected NUTS_ID, NUTS_NAME, and CNTR_CODE."
        )

    lookup = lookup.rename(
        columns={
            "NUTS_ID": "NUTS3",
            "NUTS_NAME": "NUTS3_name",
            "CNTR_CODE": "NUTS_country_code",
        }
    )
    for column in ["NUTS3", "NUTS3_name", "NUTS_country_code"]:
        lookup[column] = lookup[column].astype(str).str.strip()

    lookup = lookup.drop_duplicates(subset=["NUTS3"]).copy()
    return lookup[["NUTS3", "NUTS3_name", "NUTS_country_code"]]


def split_regions(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def transform_hanze_events(hanze_df: pd.DataFrame, nuts_lookup: pd.DataFrame) -> pd.DataFrame:
    expanded = hanze_df.copy()
    expanded["_source_row"] = range(len(expanded))
    expanded["NUTS3"] = expanded[REGIONS_COLUMN].map(split_regions)

    expanded = expanded.explode("NUTS3", ignore_index=False)
    expanded["NUTS3"] = expanded["NUTS3"].fillna("").astype(str).str.strip()
    expanded = expanded.loc[expanded["NUTS3"].ne("")].copy()
    expanded["_region_sequence"] = expanded.groupby("_source_row").cumcount() + 1

    expanded = expanded.merge(nuts_lookup, on="NUTS3", how="left")
    expanded["NUTS3_name"] = expanded["NUTS3_name"].fillna("")

    expanded = expanded.sort_values(
        ["_source_row", "_region_sequence"],
        kind="stable",
    ).reset_index(drop=True)

    insert_at = expanded.columns.get_loc(REGIONS_COLUMN) + 1
    ordered_columns = [column for column in hanze_df.columns if column in expanded.columns]
    ordered_columns[insert_at:insert_at] = ["NUTS3", "NUTS3_name"]

    return expanded[ordered_columns].copy()


def write_csv(path: str | Path, df: pd.DataFrame) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    nuts_path = Path(args.nuts)
    output_path = Path(args.output)

    hanze_df = read_hanze_csv(input_path)
    nuts_lookup = load_nuts3_lookup(nuts_path)
    transformed = transform_hanze_events(hanze_df, nuts_lookup)
    write_csv(output_path, transformed)

    unmatched_mask = transformed["NUTS3_name"].eq("")
    unmatched_codes = transformed.loc[unmatched_mask, "NUTS3"].drop_duplicates().tolist()

    print(f"Read {len(hanze_df):,} HANZE rows from {input_path.resolve()}.")
    print(f"Wrote {len(transformed):,} expanded rows to {output_path.resolve()}.")
    print(f"Expanded to {transformed['NUTS3'].nunique():,} unique NUTS3 codes.")
    print(f"Unmatched NUTS3 codes: {len(unmatched_codes):,}.")
    if unmatched_codes:
        print("Sample unmatched NUTS3 codes:", unmatched_codes[:20])


if __name__ == "__main__":
    main()
