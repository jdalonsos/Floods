from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_flood_lgd_exports import build_flood_lgd_dataframe  # noqa: E402


class BuildFloodLgdExportsTests(unittest.TestCase):
    def test_build_flood_lgd_dataframe_keeps_zero_rows_without_events(self) -> None:
        source_df = pd.DataFrame(
            {
                "point_id": [1, 2],
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
        self.assertTrue(result["Obligor_ID"].isna().all())
        self.assertTrue(result["Facility_ID"].isna().all())
        self.assertEqual(result["FLAG_FLOOD_ADR"].tolist(), [0, 0])
        self.assertEqual(result["FLAG_FLOOD_ADR_AREA"].tolist(), [0, 0])
        self.assertTrue(result["DATE_REF_FLOOD"].isna().all())
        self.assertTrue(result["DATE_END_FLOOD"].isna().all())

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
