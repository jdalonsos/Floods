from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from add_default_date_to_flood_lgd import run as run_add_default_date_to_flood_lgd  # noqa: E402
from build_flood_lgd_exports import build_flood_lgd_dataframe, load_source_frame  # noqa: E402
from build_flood_lgd_exports_italy import (  # noqa: E402
    build_italy_export_argument_parser,
    run as run_italy_export,
)
from build_flood_lgd_exports_collaterals import (  # noqa: E402
    build_collaterals_export_argument_parser,
)
from build_flood_lgd_exports_collaterals_italy import (  # noqa: E402
    build_italy_collaterals_export_argument_parser,
    run as run_italy_collaterals_export,
)


class BuildFloodLgdExportsTests(unittest.TestCase):
    def test_collaterals_export_parser_uses_expected_defaults(self) -> None:
        parser = build_collaterals_export_argument_parser()

        args = parser.parse_args(["--source-workbook", "data/raw/my_collaterals_points.xlsx"])

        self.assertEqual(args.source_point_id_col, "ID_geoloc")
        self.assertEqual(args.source_latitude_col, "lat")
        self.assertEqual(args.source_longitude_col, "lon")
        self.assertEqual(args.source_closed_default_col, "Closed_Default_Date")
        self.assertEqual(args.source_closed_default_fallback_col, "Cut_off_Date")
        self.assertEqual(args.source_default_date_col, "Default_Date")
        self.assertEqual(args.source_obligor_id_col, "Obligor_ID")
        self.assertEqual(args.source_facility_id_col, "Facility_ID")
        self.assertEqual(args.source_type_adr_value, "Collateral")
        self.assertEqual(
            Path(args.jrc_workbook),
            Path("data/processed/france_points_jrc_flood_check_collaterals.xlsx"),
        )
        self.assertEqual(
            Path(args.gaspar_workbook),
            Path("data/processed/france_points_gaspar_check_collaterals.xlsx"),
        )
        self.assertEqual(
            Path(args.hanze_workbook),
            Path("data/processed/france_points_hanze_check_collaterals.xlsx"),
        )

    def test_load_source_frame_supports_t20_style_collateral_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workbook_path = Path(tmp_dir) / "collaterals.xlsx"
            pd.DataFrame(
                {
                    "ID_geoloc": ["A-1", "A-2"],
                    "Obligor_ID": ["OBL-1", "OBL-2"],
                    "Facility_ID": ["FAC-1", "FAC-2"],
                    "lat": [48.1, 48.2],
                    "lon": [2.1, 2.2],
                    "Closed_Default_Date": [pd.Timestamp("2020-01-05"), pd.NaT],
                    "Cut_off_Date": [pd.Timestamp("2020-06-07"), pd.Timestamp("2020-02-06")],
                    "Default_Date": [pd.Timestamp("2020-03-07"), pd.Timestamp("2020-04-08")],
                }
            ).to_excel(workbook_path, index=False)

            source_df = load_source_frame(
                workbook_path,
                point_id_col="ID_geoloc",
                latitude_col="lat",
                longitude_col="lon",
                closed_default_col="Closed_Default_Date",
                closed_default_fallback_col="Cut_off_Date",
                default_type_adr="Collateral",
            )

        self.assertEqual(source_df["point_id"].tolist(), ["A-1", "A-2"])
        self.assertEqual(source_df["Obligor_ID"].tolist(), ["OBL-1", "OBL-2"])
        self.assertEqual(source_df["Facility_ID"].tolist(), ["FAC-1", "FAC-2"])
        self.assertEqual(source_df["TYPE_ADR"].tolist(), ["Collateral", "Collateral"])
        self.assertEqual(
            source_df["CLOSED_DEFAULT_DATE"].tolist(),
            [pd.Timestamp("2020-01-05"), pd.Timestamp("2020-02-06")],
        )
        self.assertEqual(
            source_df["Default_Date"].tolist(),
            [pd.Timestamp("2020-03-07"), pd.Timestamp("2020-04-08")],
        )
        self.assertEqual(
            source_df["ID_ADR"].tolist(),
            ["48.10000000, 2.10000000", "48.20000000, 2.20000000"],
        )

    def test_italy_collaterals_export_parser_uses_expected_defaults(self) -> None:
        parser = build_italy_collaterals_export_argument_parser()

        args = parser.parse_args(["--source-workbook", "data/raw/my_italy_collaterals_points.xlsx"])

        self.assertIsNone(args.source_point_id_col)
        self.assertEqual(args.source_latitude_col, "lat")
        self.assertEqual(args.source_longitude_col, "lon")
        self.assertEqual(args.source_closed_default_col, "last_date")
        self.assertEqual(args.source_facility_id_col, "KEY_COLLATERAL")
        self.assertEqual(args.source_type_adr_value, "Collateral")
        self.assertIsNone(args.gaspar_workbook)
        self.assertEqual(
            Path(args.jrc_workbook),
            Path("data/processed/italy_points_jrc_flood_check_collaterals.xlsx"),
        )
        self.assertEqual(
            Path(args.hanze_workbook),
            Path("data/processed/italy_points_hanze_tri_check_collaterals.xlsx"),
        )

    def test_italy_collaterals_export_runs_without_gaspar_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_workbook = tmp_path / "italy_collaterals.xlsx"
            jrc_workbook = tmp_path / "italy_jrc_check.xlsx"
            hanze_workbook = tmp_path / "italy_hanze_check.xlsx"
            output_dir = tmp_path / "out"

            pd.DataFrame(
                {
                    "KEY_COLLATERAL": ["COLL-001", "COLL-001"],
                    "lat": [41.09775, 41.16654],
                    "lon": [16.77685, 16.40878],
                    "last_date": [pd.Timestamp("2021-03-09"), pd.Timestamp("2022-09-21")],
                }
            ).to_excel(source_workbook, index=False)

            with pd.ExcelWriter(jrc_workbook) as writer:
                pd.DataFrame(columns=["point_id", "event_id"]).to_excel(
                    writer,
                    sheet_name="event_hits",
                    index=False,
                )

            with pd.ExcelWriter(hanze_workbook) as writer:
                pd.DataFrame(columns=["point_id", "hanze_event_uid"]).to_excel(
                    writer,
                    sheet_name="candidate_events",
                    index=False,
                )
                pd.DataFrame(columns=["point_id", "hanze_event_uid"]).to_excel(
                    writer,
                    sheet_name="event_hits",
                    index=False,
                )

            parser = build_italy_collaterals_export_argument_parser()
            args = parser.parse_args(
                [
                    "--source-workbook",
                    str(source_workbook),
                    "--jrc-workbook",
                    str(jrc_workbook),
                    "--hanze-workbook",
                    str(hanze_workbook),
                    "--output-dir",
                    str(output_dir),
                    "--mode",
                    "csv",
                    "--quiet",
                ]
            )

            run_italy_collaterals_export(args)

            output_path = output_dir / "italy_collaterals_FLOOD_LGD.csv"
            self.assertTrue(output_path.exists())

            raw_text = output_path.read_text(encoding="utf-8")
            self.assertIn(";", raw_text)
            self.assertIn("41.09775000, 16.77685000", raw_text)
            self.assertNotIn('"41.09775000, 16.77685000"', raw_text)

            result = pd.read_csv(output_path, sep=";")
            self.assertEqual(result["point_id"].tolist(), [1, 2])
            self.assertEqual(result["Facility_ID"].tolist(), ["COLL-001", "COLL-001"])
            self.assertEqual(result["FLAG_FLOOD_ADR"].tolist(), [0, 0])
            self.assertEqual(result["FLAG_FLOOD_ADR_AREA"].tolist(), [0, 0])

    def test_italy_export_parser_uses_expected_defaults(self) -> None:
        parser = build_italy_export_argument_parser()

        args = parser.parse_args([])

        self.assertEqual(Path(args.source_workbook), Path("data/processed/T20_Anonymised.xlsx"))
        self.assertEqual(args.source_point_id_col, "#")
        self.assertEqual(args.source_latitude_col, "LAT")
        self.assertEqual(args.source_longitude_col, "LONG")
        self.assertEqual(args.source_closed_default_col, "Closed_Default_Date")
        self.assertEqual(args.source_obligor_id_col, "Obligor_ID")
        self.assertEqual(args.source_facility_id_col, "Facility_ID")
        self.assertEqual(args.source_type_adr_col, "TYPE_ADR")
        self.assertIsNone(args.gaspar_workbook)
        self.assertEqual(
            Path(args.jrc_workbook),
            Path("data/processed/T20_Anonymised_italy_jrc_flood_check.xlsx"),
        )
        self.assertEqual(
            Path(args.hanze_workbook),
            Path("data/processed/T20_Anonymised_italy_hanze_tri_check.xlsx"),
        )

    def test_italy_export_runs_without_gaspar_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_workbook = tmp_path / "t20_italy.xlsx"
            jrc_workbook = tmp_path / "t20_italy_jrc_check.xlsx"
            hanze_workbook = tmp_path / "t20_italy_hanze_check.xlsx"
            output_dir = tmp_path / "out"

            pd.DataFrame(
                {
                    "#": [1001, 1002],
                    "Obligor_ID": ["OBL-1", "OBL-2"],
                    "Facility_ID": ["FAC-1", "FAC-2"],
                    "LAT": [41.09775, 41.16654],
                    "LONG": [16.77685, 16.40878],
                    "Closed_Default_Date": [pd.Timestamp("2021-03-09"), pd.Timestamp("2022-09-21")],
                    "TYPE_ADR": ["Facility", "Facility"],
                }
            ).to_excel(source_workbook, index=False)

            with pd.ExcelWriter(jrc_workbook) as writer:
                pd.DataFrame(columns=["point_id", "event_id"]).to_excel(
                    writer,
                    sheet_name="event_hits",
                    index=False,
                )

            with pd.ExcelWriter(hanze_workbook) as writer:
                pd.DataFrame(columns=["point_id", "hanze_event_uid"]).to_excel(
                    writer,
                    sheet_name="candidate_events",
                    index=False,
                )
                pd.DataFrame(columns=["point_id", "hanze_event_uid"]).to_excel(
                    writer,
                    sheet_name="event_hits",
                    index=False,
                )

            parser = build_italy_export_argument_parser()
            args = parser.parse_args(
                [
                    "--source-workbook",
                    str(source_workbook),
                    "--jrc-workbook",
                    str(jrc_workbook),
                    "--hanze-workbook",
                    str(hanze_workbook),
                    "--output-dir",
                    str(output_dir),
                    "--mode",
                    "csv",
                    "--quiet",
                ]
            )

            run_italy_export(args)

            output_path = output_dir / "t20_italy_FLOOD_LGD.csv"
            self.assertTrue(output_path.exists())

            raw_text = output_path.read_text(encoding="utf-8")
            self.assertIn(";", raw_text)
            self.assertIn("41.09775000, 16.77685000", raw_text)
            self.assertNotIn('"41.09775000, 16.77685000"', raw_text)

            result = pd.read_csv(output_path, sep=";")
            self.assertEqual(result["point_id"].tolist(), [1001, 1002])
            self.assertEqual(result["Obligor_ID"].tolist(), ["OBL-1", "OBL-2"])
            self.assertEqual(result["Facility_ID"].tolist(), ["FAC-1", "FAC-2"])
            self.assertEqual(result["FLAG_FLOOD_ADR"].tolist(), [0, 0])
            self.assertEqual(result["FLAG_FLOOD_ADR_AREA"].tolist(), [0, 0])

    def test_build_flood_lgd_dataframe_keeps_zero_rows_without_events(self) -> None:
        source_df = pd.DataFrame(
            {
                "point_id": [1, 2],
                "Default_Date": [pd.Timestamp("2020-03-07"), pd.Timestamp("2020-04-08")],
                "ID_ADR": ["48.10000000, 2.10000000", "48.20000000, 2.20000000"],
                "TYPE_ADR": ["Collateral", "Facility"],
                "point_order": [0, 1],
            }
        )

        result = build_flood_lgd_dataframe(
            source_df=source_df,
            jrc_event_hits=pd.DataFrame(),
            gaspar_candidates=pd.DataFrame(),
            gaspar_hits=pd.DataFrame(),
            hanze_candidates=pd.DataFrame(),
            hanze_hits=pd.DataFrame(),
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result["point_id"].tolist(), [1, 2])
        self.assertEqual(
            result["Default_Date"].tolist(),
            [pd.Timestamp("2020-03-07"), pd.Timestamp("2020-04-08")],
        )
        self.assertTrue(result["Obligor_ID"].isna().all())
        self.assertTrue(result["Facility_ID"].isna().all())
        self.assertEqual(result["FLAG_FLOOD_ADR"].tolist(), [0, 0])
        self.assertEqual(result["FLAG_FLOOD_ADR_AREA"].tolist(), [0, 0])
        self.assertTrue(result["DATE_REF_FLOOD"].isna().all())
        self.assertTrue(result["DATE_END_FLOOD"].isna().all())

    def test_add_default_date_to_existing_flood_lgd_csv_without_reclustering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_workbook = tmp_path / "t20_source.xlsx"
            export_csv = tmp_path / "t20_FLOOD_LGD.csv"
            output_csv = tmp_path / "t20_FLOOD_LGD_with_default_date.csv"

            pd.DataFrame(
                {
                    "#": [101, 202],
                    "Default_Date": [pd.Timestamp("2009-10-20"), pd.Timestamp("2022-09-09")],
                }
            ).to_excel(source_workbook, index=False)

            pd.DataFrame(
                {
                    "point_id": [101, 101, 202],
                    "FLAG_FLOOD_ADR": [1, 0, 1],
                    "DATE_REF_FLOOD": [
                        pd.Timestamp("2020-01-01"),
                        pd.Timestamp("2020-03-01"),
                        pd.Timestamp("2021-02-02"),
                    ],
                }
            ).to_csv(export_csv, index=False, sep=";")

            args = argparse.Namespace(
                source_workbook=str(source_workbook),
                flood_lgd_file=str(export_csv),
                output_file=str(output_csv),
                in_place=False,
                sheet_name="FLOOD_LGD",
                source_sheet_name=None,
                source_point_id_col="#",
                source_default_date_col="Default_Date",
                quiet=True,
            )

            run_add_default_date_to_flood_lgd(args)

            self.assertTrue(output_csv.exists())
            result = pd.read_csv(output_csv, sep=";")
            self.assertEqual(result.columns.tolist(), ["point_id", "Default_Date", "FLAG_FLOOD_ADR", "DATE_REF_FLOOD"])
            self.assertEqual(result["Default_Date"].tolist(), ["2009-10-20", "2009-10-20", "2022-09-09"])
            self.assertEqual(result["FLAG_FLOOD_ADR"].tolist(), [1, 0, 1])

    def test_add_default_date_to_existing_collateral_flood_lgd_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_workbook = tmp_path / "france_collaterals_source.xlsx"
            export_csv = tmp_path / "france_collaterals_FLOOD_LGD.csv"
            output_csv = tmp_path / "france_collaterals_FLOOD_LGD_with_default_date.csv"

            pd.DataFrame(
                {
                    "ID_geoloc": ["ADR-001", "ADR-002"],
                    "Default_Date": [pd.Timestamp("2018-06-30"), pd.Timestamp("2020-11-15")],
                }
            ).to_excel(source_workbook, index=False)

            pd.DataFrame(
                {
                    "point_id": ["ADR-001", "ADR-001", "ADR-002"],
                    "Facility_ID": ["COLL-A", "COLL-A", "COLL-B"],
                    "FLAG_FLOOD_ADR": [1, 0, 1],
                }
            ).to_csv(export_csv, index=False, sep=";")

            args = argparse.Namespace(
                source_workbook=str(source_workbook),
                flood_lgd_file=str(export_csv),
                output_file=str(output_csv),
                in_place=False,
                sheet_name="FLOOD_LGD",
                source_sheet_name=None,
                source_point_id_col="ID_geoloc",
                source_default_date_col="Default_Date",
                quiet=True,
            )

            run_add_default_date_to_flood_lgd(args)

            self.assertTrue(output_csv.exists())
            result = pd.read_csv(output_csv, sep=";")
            self.assertEqual(result.columns.tolist(), ["point_id", "Facility_ID", "Default_Date", "FLAG_FLOOD_ADR"])
            self.assertEqual(result["Default_Date"].tolist(), ["2018-06-30", "2018-06-30", "2020-11-15"])
            self.assertEqual(result["point_id"].tolist(), ["ADR-001", "ADR-001", "ADR-002"])

    def test_build_flood_lgd_dataframe_merges_sources_within_30_days(self) -> None:
        source_df = pd.DataFrame(
            {
                "point_id": [1],
                "Obligor_ID": ["OBL-1"],
                "Facility_ID": ["FAC-1"],
                "CLOSED_DEFAULT_DATE": [pd.Timestamp("2020-12-31")],
                "ID_ADR": ["48.10000000, 2.10000000"],
                "TYPE_ADR": ["Collateral"],
                "point_order": [0],
            }
        )
        jrc_event_hits = pd.DataFrame(
            {
                "point_id": [1],
                "event_id": ["jrc-1"],
                "start_date": [pd.Timestamp("2020-01-10")],
                "end_date": [pd.Timestamp("2020-01-15")],
                "point_buffer_flood_hit": [True],
                "buffer_flood_hit": [True],
                "point_buffer_mean_depth_cm": [12.5],
                "point_buffer_max_depth_cm": [30.0],
                "buffer_mean_depth_cm": [7.5],
                "buffer_max_depth_cm": [22.0],
            }
        )
        gaspar_candidates = pd.DataFrame(
            {
                "point_id": [1],
                "gaspar_event_uid": ["gaspar-1"],
                "gaspar_start_date": [pd.Timestamp("2020-01-01")],
                "gaspar_end_date": [pd.Timestamp("2020-01-05")],
            }
        )
        gaspar_hits = pd.DataFrame({"point_id": [1], "gaspar_event_uid": ["gaspar-1"]})
        hanze_candidates = pd.DataFrame(
            {
                "point_id": [1],
                "hanze_event_uid": ["hanze-1"],
                "hanze_start_date": [pd.Timestamp("2020-02-10")],
                "hanze_end_date": [pd.Timestamp("2020-02-12")],
            }
        )
        hanze_hits = pd.DataFrame({"point_id": [1], "hanze_event_uid": ["hanze-1"]})

        result = build_flood_lgd_dataframe(
            source_df=source_df,
            jrc_event_hits=jrc_event_hits,
            gaspar_candidates=gaspar_candidates,
            gaspar_hits=gaspar_hits,
            hanze_candidates=hanze_candidates,
            hanze_hits=hanze_hits,
            merge_gap_days=30,
        )

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(int(row["Flag_JRC"]), 1)
        self.assertEqual(int(row["Flag_GASPAR"]), 1)
        self.assertEqual(int(row["Flag_HANZE"]), 1)
        self.assertEqual(int(row["Flag_JRC_AREA"]), 1)
        self.assertEqual(int(row["Flag_GASPAR_AREA"]), 1)
        self.assertEqual(int(row["Flag_HANZE_AREA"]), 1)
        self.assertEqual(row["FLOOD_DATA_SOURCE"], "JRC")
        self.assertEqual(row["FLOOD_DATA_SOURCE_AREA"], "JRC")
        self.assertEqual(row["DATE_REF_FLOOD"], pd.Timestamp("2020-01-10"))
        self.assertEqual(row["DATE_END_FLOOD"], pd.Timestamp("2020-01-15"))
        self.assertEqual(float(row["FLOOD_DEPTH_MOY"]), 12.5)
        self.assertEqual(float(row["FLOOD_DEPTH_MOY_AREA"]), 7.5)
        self.assertEqual(float(row["FLOOD_DEPTH_MAX"]), 30.0)
        self.assertEqual(float(row["FLOOD_DEPTH_MAX_AREA"]), 22.0)

    def test_build_flood_lgd_dataframe_splits_clusters_when_gap_exceeds_30_days(self) -> None:
        source_df = pd.DataFrame(
            {
                "point_id": [1],
                "Obligor_ID": ["OBL-1"],
                "Facility_ID": ["FAC-1"],
                "CLOSED_DEFAULT_DATE": [pd.Timestamp("2020-12-31")],
                "ID_ADR": ["48.10000000, 2.10000000"],
                "TYPE_ADR": ["Collateral"],
                "point_order": [0],
            }
        )
        gaspar_candidates = pd.DataFrame(
            {
                "point_id": [1],
                "gaspar_event_uid": ["gaspar-1"],
                "gaspar_start_date": [pd.Timestamp("2020-01-01")],
                "gaspar_end_date": [pd.Timestamp("2020-01-05")],
            }
        )
        gaspar_hits = pd.DataFrame({"point_id": [1], "gaspar_event_uid": ["gaspar-1"]})
        hanze_candidates = pd.DataFrame(
            {
                "point_id": [1],
                "hanze_event_uid": ["hanze-1"],
                "hanze_start_date": [pd.Timestamp("2020-03-10")],
                "hanze_end_date": [pd.Timestamp("2020-03-12")],
            }
        )
        hanze_hits = pd.DataFrame({"point_id": [1], "hanze_event_uid": ["hanze-1"]})

        result = build_flood_lgd_dataframe(
            source_df=source_df,
            jrc_event_hits=pd.DataFrame(),
            gaspar_candidates=gaspar_candidates,
            gaspar_hits=gaspar_hits,
            hanze_candidates=hanze_candidates,
            hanze_hits=hanze_hits,
            merge_gap_days=30,
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result["FLOOD_DATA_SOURCE"].tolist(), ["GASPAR", "HANZE"])
        self.assertEqual(
            result["DATE_REF_FLOOD"].tolist(),
            [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-03-10")],
        )
        self.assertEqual(
            result["DATE_END_FLOOD"].tolist(),
            [pd.Timestamp("2020-01-05"), pd.Timestamp("2020-03-12")],
        )

    def test_build_flood_lgd_dataframe_uses_area_candidate_dates_without_point_hit(self) -> None:
        source_df = pd.DataFrame(
            {
                "point_id": [1],
                "Obligor_ID": ["OBL-1"],
                "Facility_ID": ["FAC-1"],
                "CLOSED_DEFAULT_DATE": [pd.Timestamp("2020-12-31")],
                "ID_ADR": ["48.10000000, 2.10000000"],
                "TYPE_ADR": ["Collateral"],
                "point_order": [0],
            }
        )
        hanze_candidates = pd.DataFrame(
            {
                "point_id": [1],
                "hanze_event_uid": ["hanze-1"],
                "hanze_start_date": [pd.Timestamp("2020-04-01")],
                "hanze_end_date": [pd.Timestamp("2020-04-04")],
            }
        )

        result = build_flood_lgd_dataframe(
            source_df=source_df,
            jrc_event_hits=pd.DataFrame(),
            gaspar_candidates=pd.DataFrame(),
            gaspar_hits=pd.DataFrame(),
            hanze_candidates=hanze_candidates,
            hanze_hits=pd.DataFrame(),
            merge_gap_days=30,
        )

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertTrue(pd.isna(row["FLOOD_DATA_SOURCE"]))
        self.assertEqual(row["FLOOD_DATA_SOURCE_AREA"], "HANZE")
        self.assertEqual(int(row["FLAG_FLOOD_ADR"]), 0)
        self.assertEqual(int(row["FLAG_FLOOD_ADR_AREA"]), 1)
        self.assertEqual(int(row["Flag_HANZE"]), 0)
        self.assertEqual(int(row["Flag_HANZE_AREA"]), 1)
        self.assertEqual(row["DATE_REF_FLOOD"], pd.Timestamp("2020-04-01"))
        self.assertEqual(row["DATE_END_FLOOD"], pd.Timestamp("2020-04-04"))


if __name__ == "__main__":
    unittest.main()
