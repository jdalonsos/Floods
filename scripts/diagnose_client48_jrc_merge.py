from pathlib import Path
import pandas as pd

TARGET_LAT = 48.81162111
TARGET_LON = -3.43762118

files = [
    Path("data/processed/T20_Anonymised_jrc_flood_check.xlsx"),
    Path("data/processed/T20_Anonymised_jrc_gaspar_tri_check.xlsx"),
    Path("data/processed/france_points_jrc_flood_check.xlsx"),
    Path("outputs/flood_lgd_export_fast_obligor/T20_Anonymised_jrc_flood_check_FLOOD_LGD_only.xlsx"),
    Path("outputs/flood_lgd_export_fast/T20_Anonymised_jrc_flood_check_FLOOD_LGD_only.xlsx"),
    Path("outputs/flood_lgd_export_py/T20_Anonymised_jrc_flood_check_with_FLOOD_LGD.xlsx"),
    Path("outputs/flood_lgd_export_20260617/T20_Anonymised_jrc_flood_check_with_FLOOD_LGD.xlsx"),
]

for path in files:
    if not path.exists():
        continue
    print(f"\n### {path}")
    book = pd.ExcelFile(path)
    print(book.sheet_names)
    for sheet in book.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet)
        cols = {str(c).lower(): c for c in frame.columns}
        matched = pd.DataFrame()
        lat_col = next((c for k, c in cols.items() if k in {"latitude", "lat", "y"}), None)
        lon_col = next((c for k, c in cols.items() if k in {"longitude", "lon", "lng", "x"}), None)
        if lat_col is not None and lon_col is not None:
            lat = pd.to_numeric(frame[lat_col], errors="coerce")
            lon = pd.to_numeric(frame[lon_col], errors="coerce")
            matched = frame[(lat.sub(TARGET_LAT).abs() < 1e-6) & (lon.sub(TARGET_LON).abs() < 1e-6)]
        if matched.empty:
            id_col = next((c for k, c in cols.items() if k in {"point_id", "client", "client_id", "id"}), None)
            if id_col is not None:
                values = frame[id_col].astype(str).str.strip()
                matched = frame[values.isin({"48", "48.0"})]
        if not matched.empty:
            wanted = [c for c in frame.columns if any(token in str(c).lower() for token in (
                "point", "client", "lat", "lon", "start", "end", "event", "hit", "depth", "flag", "date"
            ))]
            print(f"\nSHEET {sheet}: {len(matched)} rows")
            print(matched[wanted].to_string(index=False))
