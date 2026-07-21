from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from add_nuts_to_flood_lgd import run as run_add_nuts_to_flood_lgd  # noqa: E402


def build_test_nuts_gpkg(path: Path) -> None:
    gdf = gpd.GeoDataFrame(
        {
            "LEVL_CODE": [1, 2, 3, 1, 2, 3],
            "NUTS_ID": ["FR1", "FR10", "FR101", "FR2", "FR20", "FR201"],
            "NUTS_NAME": [
                "Paris Area",
                "Ile-de-France",
                "Paris",
                "North Area",
                "Hauts-de-France",
                "Lille",
            ],
            "CNTR_CODE": ["FR", "FR", "FR", "FR", "FR", "FR"],
            "geometry": [
                box(1.5, 48.0, 3.5, 49.5),
                box(2.0, 48.4, 2.8, 49.1),
                box(2.1, 48.7, 2.6, 48.95),
                box(2.5, 49.8, 4.2, 51.0),
                box(2.8, 50.4, 3.3, 50.9),
                box(2.95, 50.55, 3.2, 50.75),
            ],
        },
        crs="EPSG:4326",
    )
    gdf.to_file(path, driver="GPKG")


class AddNutsToFloodLgdTests(unittest.TestCase):
    def assert_csv_enrichment(self, delimiter: str) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            nuts_gpkg = tmp_path / "nuts_test.gpkg"
            export_csv = tmp_path / "france_FLOOD_LGD.csv"
            output_csv = tmp_path / "france_FLOOD_LGD_with_nuts.csv"

            build_test_nuts_gpkg(nuts_gpkg)
            pd.DataFrame(
                {
                    "point_id": [101, 202, 303],
                    "ID_ADR": [
                        "48.85660000, 2.35220000",
                        "3.05730000, 50.62920000",
                        "",
                    ],
                    "FLAG_FLOOD_ADR": [1, 1, 0],
                }
            ).to_csv(export_csv, index=False, sep=delimiter)

            args = argparse.Namespace(
                flood_lgd_file=str(export_csv),
                nuts_file=str(nuts_gpkg),
                output_file=str(output_csv),
                in_place=False,
                sheet_name="FLOOD_LGD",
                id_adr_col="ID_ADR",
                country_code="FR",
                default_coordinate_order="lat_lon",
                quiet=True,
            )

            run_add_nuts_to_flood_lgd(args)

            result = pd.read_csv(output_csv, sep=delimiter)
            self.assertEqual(
                result.columns.tolist(),
                [
                    "point_id",
                    "ID_ADR",
                    "point_latitude",
                    "point_longitude",
                    "id_adr_coordinate_order",
                    "id_adr_order_resolution",
                    "nuts1_code",
                    "nuts1_name",
                    "nuts2_code",
                    "nuts2_name",
                    "nuts3_code",
                    "nuts3_name",
                    "FLAG_FLOOD_ADR",
                ],
            )

            self.assertAlmostEqual(result.loc[0, "point_latitude"], 48.8566, places=4)
            self.assertAlmostEqual(result.loc[0, "point_longitude"], 2.3522, places=4)
            self.assertEqual(result.loc[0, "id_adr_coordinate_order"], "lat_lon")
            self.assertEqual(result.loc[0, "id_adr_order_resolution"], "nuts_match")
            self.assertEqual(result.loc[0, "nuts1_code"], "FR1")
            self.assertEqual(result.loc[0, "nuts2_code"], "FR10")
            self.assertEqual(result.loc[0, "nuts3_code"], "FR101")

            self.assertAlmostEqual(result.loc[1, "point_latitude"], 50.6292, places=4)
            self.assertAlmostEqual(result.loc[1, "point_longitude"], 3.0573, places=4)
            self.assertEqual(result.loc[1, "id_adr_coordinate_order"], "lon_lat")
            self.assertEqual(result.loc[1, "id_adr_order_resolution"], "nuts_match")
            self.assertEqual(result.loc[1, "nuts1_code"], "FR2")
            self.assertEqual(result.loc[1, "nuts2_code"], "FR20")
            self.assertEqual(result.loc[1, "nuts3_code"], "FR201")

            self.assertTrue(pd.isna(result.loc[2, "point_latitude"]))
            self.assertTrue(pd.isna(result.loc[2, "point_longitude"]))
            self.assertEqual(result.loc[2, "id_adr_coordinate_order"], "missing")
            self.assertEqual(result.loc[2, "id_adr_order_resolution"], "missing_id_adr")
            self.assertTrue(pd.isna(result.loc[2, "nuts3_code"]))

    def test_add_nuts_to_semicolon_flood_lgd_csv(self) -> None:
        self.assert_csv_enrichment(";")

    def test_add_nuts_to_comma_flood_lgd_csv(self) -> None:
        self.assert_csv_enrichment(",")


if __name__ == "__main__":
    unittest.main()
