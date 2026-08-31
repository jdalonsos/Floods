from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from affine import Affine
import numpy as np
from pyproj import CRS as PyprojCRS
import rasterio
from rasterio.transform import from_origin

from flood_preview import (
    FloodPreview,
    build_direct_native_pixel_folium_map,
    build_folium_map,
    build_tiled_folium_map,
    estimate_preview_polygon_count,
    query_native_raster_pixel,
)


def make_preview(values: np.ma.MaskedArray) -> FloodPreview:
    return FloodPreview(
        tif_path=PROJECT_ROOT / "dummy.tif",
        values=values,
        display_transform=Affine(1, 0, 0, 0, -1, 2),
        bounds_latlon=[[0.0, 0.0], [2.0, 4.0]],
        full_bounds_latlon=[[0.0, 0.0], [2.0, 4.0]],
        coarse_shape=values.shape,
        display_shape=values.shape,
        source_window_shape=values.shape,
        src_height=values.shape[0],
        src_width=values.shape[1],
        crs="EPSG:4326",
        nodata=None,
        vmin=0.0,
        vmax=3.0,
        active_pixel_count=int(values.count()),
        source_window=(0, 0, values.shape[0], values.shape[1]),
        coarse_active_pixels=[],
    )


class FloodPreviewModeTests(unittest.TestCase):
    def test_direct_native_map_exports_visible_pixels_and_cluster_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tif_path = Path(temp_dir) / "projected_flood.tif"
            values = np.array([[0, 10], [20, 9999]], dtype=np.uint16)
            with rasterio.open(
                    tif_path,
                    "w",
                    driver="GTiff",
                    width=2,
                    height=2,
                    count=1,
                    dtype=values.dtype,
                    crs=PyprojCRS.from_epsg(3857).to_wkt(),
                    transform=from_origin(200000, 6000000, 20, 20),
                    nodata=0,
            ) as dst:
                dst.write(values, 1)

            with patch("flood_preview.Transformer.from_crs") as transformer_factory:
                transformer_factory.return_value.transform.side_effect = (
                    lambda xs, ys: (xs, ys)
                )
                flood_map = build_direct_native_pixel_folium_map(tif_path)
                html = flood_map.get_root().render()
                clicked = query_native_raster_pixel(
                    tif_path,
                    latitude=5_999_990,
                    longitude=200_030,
                )

        self.assertEqual(html.count("L.polygon("), 2)
        self.assertIn("Flooded native pixels", html)
        self.assertNotIn(".setView([", html)
        self.assertIn('"zoom": 12', html)
        self.assertIn("Direct native-pixel rendering: 2 source cells", html)
        self.assertIn("Flood depth: 10.0 cm", html)
        self.assertIn("Native pixel: row 0, column 1", html)
        self.assertTrue(clicked["is_flooded"])
        self.assertEqual(clicked["depth_cm"], 10.0)
        self.assertEqual((clicked["row"], clicked["column"]), (0, 1))

    def test_tiled_map_uses_lightweight_tile_layer(self) -> None:
        flood_map = build_tiled_folium_map(
            tile_url="http://127.0.0.1:9999/api/tiles/{z}/{x}/{y}.png",
            bounds_latlon=[[48.0, 4.0], [49.0, 5.0]],
            opacity=0.85,
        )
        html = flood_map.get_root().render()

        self.assertIn("api/tiles/{z}/{x}/{y}.png", html)
        self.assertIn("nearest-neighbour tiles", html)
        self.assertIn('"opacity": 0.85', html)

    def test_estimate_preview_polygon_count_uses_color_runs(self) -> None:
        values = np.ma.masked_array(
            np.array(
                [
                    [1.0, 1.0, 2.0, 0.0],
                    [1.0, 2.0, 2.0, 3.0],
                ],
                dtype=np.float32,
            ),
            mask=np.array(
                [
                    [False, False, False, True],
                    [False, False, False, False],
                ]
            ),
        )
        preview = make_preview(values)

        self.assertEqual(estimate_preview_polygon_count(preview, color_bins=4), 5)

    def test_auto_prefers_preview_polygons_before_raster_overlay(self) -> None:
        values = np.ma.masked_array(
            np.array(
                [
                    [1.0, 1.0, 2.0, 0.0],
                    [1.0, 2.0, 2.0, 3.0],
                ],
                dtype=np.float32,
            ),
            mask=np.array(
                [
                    [False, False, False, True],
                    [False, False, False, False],
                ]
            ),
        )
        preview = make_preview(values)

        with (
            patch("flood_preview.add_pixel_polygons", return_value=False) as add_exact_pixels,
            patch("flood_preview.add_preview_pixel_polygons", return_value=True) as add_preview_polygons,
            patch("flood_preview.reproject_preview_rgba_to_web") as add_raster_overlay,
        ):
            build_folium_map(
                preview,
                mode="auto",
                pixel_mode_max_cells=5,
                exact_native_pixel_limit=4,
            )

        add_exact_pixels.assert_not_called()
        add_preview_polygons.assert_called_once()
        self.assertEqual(add_preview_polygons.call_args.kwargs["max_polygons"], 5)
        add_raster_overlay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
