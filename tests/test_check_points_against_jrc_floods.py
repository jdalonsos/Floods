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

from check_points_against_jrc_floods import (  # noqa: E402
    LONGITUDE_ALIASES,
    PointColumns,
    build_summary_table,
    build_row_level_study_periods,
    filter_candidate_events_by_row_study_period,
    resolve_named_column,
)


class CheckPointsAgainstJrcFloodsTests(unittest.TestCase):
    def test_longitude_aliases_accept_long(self) -> None:
        df = pd.DataFrame(columns=["LAT", "LONG"])
        self.assertEqual(resolve_named_column(df, None, LONGITUDE_ALIASES), "LONG")

    def test_build_row_level_study_periods_uses_fallback_end_date(self) -> None:
        points_df = pd.DataFrame(
            {
                "Reference_Date": ["31/12/2008", "31/12/2011"],
                "Closed_Default_Date": ["08/10/2013", pd.NA],
                "Cut_off_Date": ["31/12/2024", "31/12/2024"],
            }
        )

        result, resolved = build_row_level_study_periods(
            points_df,
            anchor_col="Reference_Date",
            end_col="Closed_Default_Date",
            fallback_end_col="Cut_off_Date",
            lookback_years=5,
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.anchor, "Reference_Date")
        self.assertEqual(resolved.primary_end, "Closed_Default_Date")
        self.assertEqual(resolved.fallback_end, "Cut_off_Date")
        self.assertEqual(result.loc[0, "study_period_start"], pd.Timestamp("2003-12-31"))
        self.assertEqual(result.loc[0, "study_period_end"], pd.Timestamp("2013-10-08"))
        self.assertEqual(result.loc[0, "study_period_end_source"], "Closed_Default_Date")
        self.assertEqual(result.loc[1, "study_period_start"], pd.Timestamp("2006-12-31"))
        self.assertEqual(result.loc[1, "study_period_end"], pd.Timestamp("2024-12-31"))
        self.assertEqual(result.loc[1, "study_period_end_source"], "Cut_off_Date")

    def test_filter_candidate_events_by_row_study_period_is_point_specific(self) -> None:
        candidate_df = pd.DataFrame(
            {
                "point_id": [1, 1, 1, 2, 3],
                "event_id": ["too_early", "overlap", "too_late", "fallback_match", pd.NA],
                "start_date": pd.to_datetime(
                    ["2001-01-01", "2008-02-01", "2014-01-01", "2020-05-01", pd.NaT]
                ),
                "end_date": pd.to_datetime(
                    ["2002-01-01", "2008-03-01", "2014-02-01", "2020-05-20", pd.NaT]
                ),
                "study_period_start": pd.to_datetime(
                    ["2003-12-31", "2003-12-31", "2003-12-31", "2006-12-31", pd.NaT]
                ),
                "study_period_end": pd.to_datetime(
                    ["2013-10-08", "2013-10-08", "2013-10-08", "2024-12-31", pd.NaT]
                ),
            }
        )

        filtered = filter_candidate_events_by_row_study_period(candidate_df)

        self.assertEqual(filtered["event_id"].fillna("missing").tolist(), ["overlap", "fallback_match", "missing"])

    def test_build_summary_table_handles_no_positive_hits(self) -> None:
        original_points = pd.DataFrame(
            {
                "point_id": [1],
                "LAT": [48.8566],
                "LONG": [2.3522],
            }
        )
        points_with_lau = pd.DataFrame(
            {
                "point_id": [1],
                "excel_row_number": [2],
                "lau_code": ["FR_75056"],
                "lau_code_local": ["75056"],
                "lau_name": ["Paris"],
                "country_code": ["FR"],
            }
        )
        candidate_df = pd.DataFrame(
            {
                "point_id": [1],
                "event_id": ["event-1"],
                "start_date": pd.to_datetime(["2020-01-01"]),
                "end_date": pd.to_datetime(["2020-01-03"]),
                "raster_path_found": [True],
            }
        )
        inspected_df = pd.DataFrame(
            {
                "point_id": [1],
                "event_id": ["event-1"],
                "hit_at_point": [False],
                "exact_point_depth_cm": [pd.NA],
                "buffer_flood_hit": [False],
                "buffer_flooded_pixels": [0],
                "buffer_flooded_area_m2": [0.0],
                "buffer_max_depth_cm": [pd.NA],
                "buffer_median_depth_cm": [pd.NA],
                "buffer_mean_depth_cm": [pd.NA],
            }
        )

        summary = build_summary_table(
            original_points=original_points,
            point_columns=PointColumns(latitude="LAT", longitude="LONG", point_id="point_id", city=None),
            points_with_lau=points_with_lau,
            candidate_df=candidate_df,
            inspected_df=inspected_df,
            buffer_km=2.0,
            threshold_cm=0.0,
            study_start=None,
            study_end=None,
        )

        self.assertFalse(bool(summary.loc[0, "jrc_flood_hit"]))
        self.assertEqual(summary.loc[0, "jrc_flood_flag"], "no")


if __name__ == "__main__":
    unittest.main()
