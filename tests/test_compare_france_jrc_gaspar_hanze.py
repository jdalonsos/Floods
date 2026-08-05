import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compare_france_jrc_gaspar_hanze import build_triple_matches, interval_match, parse_hanze_dates


class ThreeSourceComparisonTests(unittest.TestCase):
    def test_parse_hanze_dates_supports_mixed_iso_and_french_dates(self):
        result = parse_hanze_dates(pd.Series(["2024-01-02", "29/03/2024"]))
        self.assertEqual(result.dt.strftime("%Y-%m-%d").tolist(), ["2024-01-02", "2024-03-29"])

    def test_interval_match_requires_same_nuts3_and_respects_window(self):
        left = pd.DataFrame(
            {
                "event_id": ["j1", "j2"],
                "nuts3_code": ["FR101", "FR102"],
                "start_date": pd.to_datetime(["2020-01-01", "2020-01-01"]),
                "end_date": pd.to_datetime(["2020-01-02", "2020-01-02"]),
            }
        )
        right = pd.DataFrame(
            {
                "event_id": ["g1", "g2"],
                "nuts3_code": ["FR101", "FR102"],
                "start_date": pd.to_datetime(["2020-01-10", "2020-03-01"]),
                "end_date": pd.to_datetime(["2020-01-11", "2020-03-02"]),
            }
        )
        result = interval_match(left, right, "jrc", "gaspar", 10)
        self.assertEqual(result[["jrc_event_id", "gaspar_event_id"]].values.tolist(), [["j1", "g1"]])

    def test_triple_match_requires_all_three_pairwise_links(self):
        jg = pd.DataFrame({"jrc_event_id": ["j1"], "gaspar_event_id": ["g1"], "nuts3_code": ["FR101"]})
        jh = pd.DataFrame({"jrc_event_id": ["j1"], "hanze_event_id": ["h1"], "nuts3_code": ["FR101"]})
        gh = pd.DataFrame({"gaspar_event_id": ["g1"], "hanze_event_id": ["h1"], "nuts3_code": ["FR101"]})
        result = build_triple_matches(jg, jh, gh)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "hanze_event_id"], "h1")


if __name__ == "__main__":
    unittest.main()
