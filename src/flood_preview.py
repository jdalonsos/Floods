"""Efficient flood-raster discovery and preview helpers.

These utilities keep the heavy TIFF workflow practical by:
- scanning only official JRC raster filenames
- locating the flood signal with a coarse pass first
- reading only a detailed local crop afterward
- switching between exact native pixels and a lighter raster overlay
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Optional

from affine import Affine
import folium
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject
from rasterio.windows import Window


OFFICIAL_FILENAME_RE = re.compile(
    r"^WD_MERGE_"
    r"(?P<start_date>\d{4}-\d{2}-\d{2})---(?P<end_date>\d{4}-\d{2}-\d{2})"
    r"_duration_(?P<duration_days>\d+)_days"
    r"_cluster_(?P<flood_id>\d+)"
    r"_A0_(?P<gfm_extent_km2>\d+)"
    r"_A_(?P<enhanced_extent_km2>\d+)"
    r"_lat_(?P<centroid_lat_cents>-?\d+)"
    r"_lon_(?P<centroid_lon_cents>-?\d+)"
    r"_size_(?P<spatial_spread_units>\d+)"
    r"\.(?:tif|tiff)$",
    flags=re.IGNORECASE,
)

YEAR_DIR_RE = re.compile(r"^(?P<year>\d{4})(?:_filtered)?$")


@dataclass(frozen=True)
class FloodRasterFile:
    path: Path
    raster_file: str
    year: Optional[int]
    start_date: str
    end_date: str
    duration_days: int
    flood_id: int
    gfm_extent_km2: int
    enhanced_extent_km2: int
    centroid_lat_cents: int
    centroid_lon_cents: int
    spatial_spread_units: int

    @property
    def event_id(self) -> str:
        return self.path.stem

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "raster_file": self.raster_file,
            "event_id": self.event_id,
            "year": self.year,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "duration_days": self.duration_days,
            "flood_id": self.flood_id,
            "gfm_extent_km2": self.gfm_extent_km2,
            "enhanced_extent_km2": self.enhanced_extent_km2,
            "centroid_lat_cents": self.centroid_lat_cents,
            "centroid_lon_cents": self.centroid_lon_cents,
            "spatial_spread_units": self.spatial_spread_units,
        }


@dataclass
class FloodPreview:
    tif_path: Path
    values: np.ma.MaskedArray
    display_transform: Affine
    bounds_latlon: list[list[float]]
    full_bounds_latlon: list[list[float]]
    coarse_shape: tuple[int, int]
    display_shape: tuple[int, int]
    source_window_shape: tuple[int, int]
    src_height: int
    src_width: int
    crs: str
    nodata: float | None
    vmin: float
    vmax: float
    active_pixel_count: int
    source_window: tuple[int, int, int, int]
    coarse_active_pixels: list[tuple[int, int]]


def infer_year_from_path(path: Path) -> Optional[int]:
    for part in path.parts:
        match = YEAR_DIR_RE.match(part)
        if match:
            return int(match.group("year"))
    return None


def parse_official_flood_raster(path: str | Path) -> Optional[FloodRasterFile]:
    path = Path(path)
    match = OFFICIAL_FILENAME_RE.match(path.name)
    if not match:
        return None

    meta = match.groupdict()
    return FloodRasterFile(
        path=path.resolve(),
        raster_file=path.name,
        year=infer_year_from_path(path),
        start_date=meta["start_date"],
        end_date=meta["end_date"],
        duration_days=int(meta["duration_days"]),
        flood_id=int(meta["flood_id"]),
        gfm_extent_km2=int(meta["gfm_extent_km2"]),
        enhanced_extent_km2=int(meta["enhanced_extent_km2"]),
        centroid_lat_cents=int(meta["centroid_lat_cents"]),
        centroid_lon_cents=int(meta["centroid_lon_cents"]),
        spatial_spread_units=int(meta["spatial_spread_units"]),
    )


def discover_flood_raster_files(flood_dir: str | Path) -> list[FloodRasterFile]:
    root = Path(flood_dir)
    if not root.exists():
        raise FileNotFoundError(f"Raster directory not found: {root}")

    year_dirs = [
        path for path in sorted(root.iterdir()) if path.is_dir() and YEAR_DIR_RE.match(path.name)
    ]
    candidate_dirs = year_dirs if year_dirs else [root]

    discovered: list[FloodRasterFile] = []
    for directory in candidate_dirs:
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".tif", ".tiff"}:
                continue
            parsed = parse_official_flood_raster(path)
            if parsed is not None:
                discovered.append(parsed)

    discovered.sort(
        key=lambda item: (
            item.year if item.year is not None else 0,
            item.start_date,
            item.end_date,
            item.flood_id,
            item.raster_file,
        )
    )
    return discovered


def xy_bounds_to_latlon(
    left: float,
    bottom: float,
    right: float,
    top: float,
    src_crs: Any,
    samples_per_edge: int = 41,
) -> list[list[float]]:
    xs = np.concatenate(
        [
            np.linspace(left, right, samples_per_edge),
            np.full(samples_per_edge, right),
            np.linspace(right, left, samples_per_edge),
            np.full(samples_per_edge, left),
        ]
    )
    ys = np.concatenate(
        [
            np.full(samples_per_edge, bottom),
            np.linspace(bottom, top, samples_per_edge),
            np.full(samples_per_edge, top),
            np.linspace(top, bottom, samples_per_edge),
        ]
    )
    transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    lons, lats = transformer.transform(xs, ys)
    return [
        [float(np.min(lats)), float(np.min(lons))],
        [float(np.max(lats)), float(np.max(lons))],
    ]


def raster_bounds_to_latlon(src: rasterio.io.DatasetReader) -> list[list[float]]:
    left, bottom, right, top = src.bounds
    return xy_bounds_to_latlon(left, bottom, right, top, src.crs)


def build_mask(
    data: np.ndarray,
    nodata: float | None,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
) -> np.ndarray:
    mask = np.zeros(data.shape, dtype=bool)
    if nodata is not None:
        mask |= data == nodata
    for value in mask_values:
        mask |= data == value
    mask |= data <= threshold_cm
    return mask


def build_mask_from_masked(
    data: np.ma.MaskedArray,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
) -> np.ndarray:
    """Build a flood mask while preserving nodata that GDAL already masked.

    The coarse scan and downsampled preview need flood-preserving resampling.
    A masked read with ``Resampling.average`` keeps nodata masked while making
    any output cell positive whenever any positive flood depth contributes to
    that destination footprint.
    """

    filled = np.ma.filled(data, fill_value=threshold_cm)
    mask = np.ma.getmaskarray(data).copy()
    for value in mask_values:
        mask |= filled == value
    mask |= filled <= threshold_cm
    return mask


def find_source_window(
    src: rasterio.io.DatasetReader,
    coarse_max_size: int = 1200,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
    padding_pixels: int = 600,
) -> tuple[Window, tuple[int, int], list[tuple[int, int]]]:
    scale = min(coarse_max_size / max(src.height, src.width), 1.0)
    coarse_h = max(1, int(round(src.height * scale)))
    coarse_w = max(1, int(round(src.width * scale)))

    coarse_data = src.read(
        1,
        out_shape=(coarse_h, coarse_w),
        resampling=Resampling.average,
        masked=True,
    ).astype(np.float32, copy=False)
    coarse_mask = build_mask_from_masked(
        coarse_data,
        threshold_cm=threshold_cm,
        mask_values=mask_values,
    )
    active_rows, active_cols = np.where(~coarse_mask)
    if active_rows.size == 0:
        raise ValueError("No positive flood pixels remain after masking.")

    row_scale = src.height / coarse_h
    col_scale = src.width / coarse_w

    src_row_min = max(int(np.floor(active_rows.min() * row_scale)) - padding_pixels, 0)
    src_row_max = min(
        int(np.ceil((active_rows.max() + 1) * row_scale)) + padding_pixels,
        src.height,
    )
    src_col_min = max(int(np.floor(active_cols.min() * col_scale)) - padding_pixels, 0)
    src_col_max = min(
        int(np.ceil((active_cols.max() + 1) * col_scale)) + padding_pixels,
        src.width,
    )

    window = Window(
        col_off=src_col_min,
        row_off=src_row_min,
        width=src_col_max - src_col_min,
        height=src_row_max - src_row_min,
    )
    coarse_active_pixels = list(zip(active_rows.astype(int).tolist(), active_cols.astype(int).tolist()))
    return window, (coarse_h, coarse_w), coarse_active_pixels


def read_window_preview(
    src: rasterio.io.DatasetReader,
    window: Window,
    detail_max_size: int = 1800,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
    upper_quantile: float = 0.995,
) -> tuple[np.ma.MaskedArray, Affine, list[list[float]], float, float]:
    win_h = int(window.height)
    win_w = int(window.width)
    scale = min(detail_max_size / max(win_h, win_w), 1.0)
    out_h = max(1, int(round(win_h * scale)))
    out_w = max(1, int(round(win_w * scale)))

    data = src.read(
        1,
        window=window,
        out_shape=(out_h, out_w),
        resampling=Resampling.average,
        masked=True,
    ).astype(np.float32, copy=False)

    mask = build_mask_from_masked(data, threshold_cm=threshold_cm, mask_values=mask_values)
    masked = np.ma.masked_array(data, mask=mask)
    valid = masked.compressed()
    if valid.size == 0:
        raise ValueError("No positive flood pixels remain inside the detailed crop.")

    vmin = float(valid.min())
    vmax = float(np.quantile(valid, upper_quantile))
    if vmax <= vmin:
        vmax = float(valid.max())

    window_transform = src.window_transform(window)
    display_transform = window_transform * Affine.scale(win_w / out_w, win_h / out_h)

    left, top = display_transform * (0, 0)
    right, bottom = display_transform * (out_w, out_h)
    bounds_latlon = xy_bounds_to_latlon(
        left=min(left, right),
        bottom=min(bottom, top),
        right=max(left, right),
        top=max(bottom, top),
        src_crs=src.crs,
    )

    return masked, display_transform, bounds_latlon, vmin, vmax


def read_flood_preview(
    tif_path: str | Path,
    coarse_max_size: int = 1200,
    detail_max_size: int = 1800,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
    source_padding_pixels: int = 600,
    upper_quantile: float = 0.995,
) -> FloodPreview:
    tif_path = Path(tif_path)
    with rasterio.open(tif_path) as src:
        full_bounds_latlon = raster_bounds_to_latlon(src)
        window, coarse_shape, coarse_active_pixels = find_source_window(
            src,
            coarse_max_size=coarse_max_size,
            threshold_cm=threshold_cm,
            mask_values=mask_values,
            padding_pixels=source_padding_pixels,
        )
        masked, display_transform, bounds_latlon, vmin, vmax = read_window_preview(
            src,
            window,
            detail_max_size=detail_max_size,
            threshold_cm=threshold_cm,
            mask_values=mask_values,
            upper_quantile=upper_quantile,
        )

        return FloodPreview(
            tif_path=tif_path,
            values=masked,
            display_transform=display_transform,
            bounds_latlon=bounds_latlon,
            full_bounds_latlon=full_bounds_latlon,
            coarse_shape=coarse_shape,
            display_shape=masked.shape,
            source_window_shape=(int(window.height), int(window.width)),
            src_height=src.height,
            src_width=src.width,
            crs=str(src.crs),
            nodata=src.nodata,
            vmin=vmin,
            vmax=vmax,
            active_pixel_count=int(masked.count()),
            source_window=(int(window.row_off), int(window.col_off), int(window.height), int(window.width)),
            coarse_active_pixels=coarse_active_pixels,
        )


def _get_colormap(cmap_name: str):
    try:
        return mpl.colormaps[cmap_name]
    except Exception:
        return mpl.cm.get_cmap(cmap_name)


def preview_to_rgba(preview: FloodPreview, cmap_name: str = "turbo") -> np.ndarray:
    cmap = _get_colormap(cmap_name)
    norm = mpl.colors.Normalize(vmin=preview.vmin, vmax=preview.vmax, clip=True)
    filled = preview.values.filled(preview.vmin)
    normalized = norm(filled)
    rgba = cmap(normalized)
    alpha = 0.55 + np.clip(normalized, 0.0, 1.0) * 0.40
    rgba[..., 3] = np.where(preview.values.mask, 0.0, alpha)
    return (rgba * 255).astype(np.uint8)


def reproject_preview_rgba_to_web(
    preview: FloodPreview,
    cmap_name: str = "turbo",
) -> tuple[np.ndarray, list[list[float]]]:
    """Reproject the preview crop to EPSG:4326 before drawing an image overlay.

    Folium ImageOverlay assumes the image is axis-aligned in the map CRS.
    For these flood rasters, that assumption is wrong unless we first warp the
    preview from the projected flood CRS into EPSG:4326.
    """

    src_crs = rasterio.CRS.from_string(preview.crs)
    src_h, src_w = preview.display_shape
    src_left, src_bottom, src_right, src_top = array_bounds(
        src_h,
        src_w,
        preview.display_transform,
    )

    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs,
        "EPSG:4326",
        src_w,
        src_h,
        left=src_left,
        bottom=src_bottom,
        right=src_right,
        top=src_top,
    )
    dst_h = max(int(dst_h), 1)
    dst_w = max(int(dst_w), 1)

    sentinel = np.float32(-9999.0)
    src_data = preview.values.filled(sentinel).astype(np.float32, copy=False)
    src_valid = (~preview.values.mask).astype(np.uint8)

    dst_data = np.full((dst_h, dst_w), sentinel, dtype=np.float32)
    dst_valid = np.zeros((dst_h, dst_w), dtype=np.uint8)

    reproject(
        source=src_data,
        destination=dst_data,
        src_transform=preview.display_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        src_nodata=sentinel,
        dst_nodata=sentinel,
        resampling=Resampling.nearest,
    )
    reproject(
        source=src_valid,
        destination=dst_valid,
        src_transform=preview.display_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        src_nodata=0,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )

    dst_mask = (dst_valid == 0) | (dst_data == sentinel)
    dst_preview = FloodPreview(
        tif_path=preview.tif_path,
        values=np.ma.masked_array(dst_data, mask=dst_mask),
        display_transform=dst_transform,
        bounds_latlon=[
            [float(dst_transform.f + dst_transform.e * dst_h), float(dst_transform.c)],
            [float(dst_transform.f), float(dst_transform.c + dst_transform.a * dst_w)],
        ],
        full_bounds_latlon=preview.full_bounds_latlon,
        coarse_shape=preview.coarse_shape,
        display_shape=(dst_h, dst_w),
        source_window_shape=preview.source_window_shape,
        src_height=preview.src_height,
        src_width=preview.src_width,
        crs="EPSG:4326",
        nodata=None,
        vmin=preview.vmin,
        vmax=preview.vmax,
        active_pixel_count=int((~dst_mask).sum()),
        source_window=preview.source_window,
        coarse_active_pixels=preview.coarse_active_pixels,
    )
    return preview_to_rgba(dst_preview, cmap_name=cmap_name), dst_preview.bounds_latlon


def create_static_preview_figure(
    preview: FloodPreview,
    cmap_name: str = "turbo",
    figsize: tuple[float, float] = (8.5, 8.5),
):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor("black")
    image = ax.imshow(preview.values, cmap=cmap_name, vmin=preview.vmin, vmax=preview.vmax)
    ax.set_title(preview.tif_path.name)
    ax.axis("off")
    cbar = fig.colorbar(image, ax=ax, shrink=0.75)
    cbar.set_label("Flood depth (cm)")
    fig.tight_layout()
    return fig


def extract_exact_native_pixels(
    preview: FloodPreview,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
    max_cells: int = 12000,
) -> Optional[tuple[Affine, list[tuple[int, int, float]]]]:
    row_scale = preview.src_height / preview.coarse_shape[0]
    col_scale = preview.src_width / preview.coarse_shape[1]
    seen_cells: dict[tuple[int, int], float] = {}

    with rasterio.open(preview.tif_path) as src:
        for coarse_row, coarse_col in preview.coarse_active_pixels:
            src_row_min = int(np.floor(coarse_row * row_scale))
            src_row_max = int(np.ceil((coarse_row + 1) * row_scale))
            src_col_min = int(np.floor(coarse_col * col_scale))
            src_col_max = int(np.ceil((coarse_col + 1) * col_scale))
            window = Window(
                col_off=src_col_min,
                row_off=src_row_min,
                width=max(1, src_col_max - src_col_min),
                height=max(1, src_row_max - src_row_min),
            )
            data = src.read(1, window=window, masked=False).astype(np.float32, copy=False)
            mask = build_mask(data, src.nodata, threshold_cm=threshold_cm, mask_values=mask_values)
            active_rows, active_cols = np.where(~mask)
            for row, col in zip(active_rows, active_cols):
                abs_row = int(src_row_min + row)
                abs_col = int(src_col_min + col)
                cell_id = (abs_row, abs_col)
                if cell_id in seen_cells:
                    continue
                if len(seen_cells) >= max_cells:
                    return None
                seen_cells[cell_id] = float(data[row, col])

        if not seen_cells:
            return None

        exact_pixels = [
            (row, col, value) for (row, col), value in sorted(seen_cells.items())
        ]
        return src.transform, exact_pixels


def add_pixel_polygons(
    flood_map: folium.Map,
    preview: FloodPreview,
    cmap_name: str = "turbo",
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
    max_cells: int = 12000,
) -> bool:
    extracted = extract_exact_native_pixels(
        preview,
        threshold_cm=threshold_cm,
        mask_values=mask_values,
        max_cells=max_cells,
    )
    if extracted is None:
        return False

    src_transform, exact_pixels = extracted
    transformer = Transformer.from_crs(preview.crs, "EPSG:4326", always_xy=True)
    cmap = _get_colormap(cmap_name)
    norm = mpl.colors.Normalize(vmin=preview.vmin, vmax=preview.vmax, clip=True)

    for row, col, value in exact_pixels:
        left, top = src_transform * (col, row)
        right, bottom = src_transform * (col + 1, row + 1)
        corners_x = [left, right, right, left]
        corners_y = [top, top, bottom, bottom]
        lons, lats = transformer.transform(corners_x, corners_y)
        polygon = list(zip(lats, lons))
        color = mpl.colors.to_hex(cmap(norm(value)))

        folium.Polygon(
            locations=polygon,
            color="#111111",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=f"Depth: {value:.1f} cm",
        ).add_to(flood_map)
    return True


def add_preview_pixel_polygons(
    flood_map: folium.Map,
    preview: FloodPreview,
    cmap_name: str = "turbo",
    max_cells: int = 20000,
    color_bins: int = 48,
) -> bool:
    """Draw polygons from the downsampled preview grid itself.

    This is a good compromise when exact native pixels would be too many for the
    browser, but an image overlay would introduce visible placement drift on the
    web map.
    """

    if preview.active_pixel_count > max_cells:
        return False

    active_mask = ~preview.values.mask
    value_range = preview.vmax - preview.vmin
    if value_range <= 0:
        value_range = 1.0

    transformer = Transformer.from_crs(preview.crs, "EPSG:4326", always_xy=True)
    cmap = _get_colormap(cmap_name)
    palette = [
        mpl.colors.to_hex(cmap(bin_idx / max(color_bins - 1, 1)))
        for bin_idx in range(color_bins)
    ]
    normalized = np.clip((preview.values.data - preview.vmin) / value_range, 0.0, 1.0)
    binned_values = np.full(preview.values.shape, -1, dtype=np.int16)
    binned_values[active_mask] = np.minimum(
        (normalized[active_mask] * max(color_bins - 1, 1)).astype(np.int16),
        color_bins - 1,
    )

    active_rows = np.flatnonzero(active_mask.any(axis=1))
    for row in active_rows.tolist():
        cols = np.flatnonzero(active_mask[row])
        row_bins = binned_values[row, cols]
        run_start = 0
        for idx in range(1, cols.size + 1):
            run_break = (
                idx == cols.size
                or cols[idx] != cols[idx - 1] + 1
                or row_bins[idx] != row_bins[idx - 1]
            )
            if not run_break:
                continue

            col_start = int(cols[run_start])
            col_end = int(cols[idx - 1])
            color = palette[int(row_bins[run_start])]

            left, top = preview.display_transform * (col_start, row)
            right, bottom = preview.display_transform * (col_end + 1, row + 1)
            corners_x = [left, right, right, left]
            corners_y = [top, top, bottom, bottom]
            lons, lats = transformer.transform(corners_x, corners_y)
            polygon = list(zip(lats, lons))

            folium.Polygon(
                locations=polygon,
                stroke=False,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
            ).add_to(flood_map)
            run_start = idx
    return True


def build_folium_map(
    preview: FloodPreview,
    cmap_name: str = "turbo",
    tiles: str = "CartoDB positron",
    mode: str = "auto",
    pixel_mode_max_cells: int = 15000,
    threshold_cm: float = 0.0,
    mask_values: tuple[float, ...] = (9999,),
    exact_native_pixel_limit: int = 12000,
) -> folium.Map:
    lat_center = (preview.bounds_latlon[0][0] + preview.bounds_latlon[1][0]) / 2
    lon_center = (preview.bounds_latlon[0][1] + preview.bounds_latlon[1][1]) / 2
    flood_map = folium.Map(
        location=[lat_center, lon_center],
        zoom_start=9,
        tiles=tiles,
        prefer_canvas=True,
    )

    chosen_mode = mode
    if mode == "auto":
        chosen_mode = "pixels" if preview.active_pixel_count <= pixel_mode_max_cells else "raster"

    if chosen_mode == "pixels":
        pixels_added = add_pixel_polygons(
            flood_map,
            preview,
            cmap_name=cmap_name,
            threshold_cm=threshold_cm,
            mask_values=mask_values,
            max_cells=exact_native_pixel_limit,
        )
        if not pixels_added:
            preview_pixels_added = add_preview_pixel_polygons(
                flood_map,
                preview,
                cmap_name=cmap_name,
                max_cells=pixel_mode_max_cells,
            )
            chosen_mode = "preview_pixels" if preview_pixels_added else "raster_fallback"

    if chosen_mode != "pixels":
        if chosen_mode in {"raster", "raster_fallback"}:
            rgba, overlay_bounds = reproject_preview_rgba_to_web(
                preview,
                cmap_name=cmap_name,
            )
            folium.raster_layers.ImageOverlay(
                image=rgba,
                bounds=overlay_bounds,
                opacity=1.0,
                name="Flood depth preview",
                interactive=True,
                cross_origin=False,
            ).add_to(flood_map)

    folium.LayerControl(collapsed=False).add_to(flood_map)
    flood_map.fit_bounds(preview.bounds_latlon)

    caption = (
        f"<div style='position: fixed; bottom: 18px; left: 18px; z-index: 9999; "
        f"background: white; padding: 10px 12px; border: 1px solid #999; font-size: 12px;'>"
        f"<b>{preview.tif_path.name}</b><br>"
        f"Render mode: {chosen_mode}<br>"
        f"Active preview pixels: {preview.active_pixel_count:,}<br>"
        f"Coarse active pixels: {len(preview.coarse_active_pixels):,}<br>"
        f"Detailed crop preview: {preview.display_shape[1]} x {preview.display_shape[0]} px<br>"
        f"Detailed source window: {preview.source_window_shape[1]} x {preview.source_window_shape[0]} px<br>"
        f"Full raster: {preview.src_width} x {preview.src_height} px<br>"
        f"Depth range shown: {preview.vmin:.1f} to {preview.vmax:.1f} cm"
        f"</div>"
    )
    flood_map.get_root().html.add_child(folium.Element(caption))
    return flood_map


def preview_summary(preview: FloodPreview) -> dict[str, Any]:
    return {
        "file": str(preview.tif_path),
        "crs": preview.crs,
        "nodata": preview.nodata,
        "source_shape": (preview.src_height, preview.src_width),
        "coarse_shape": preview.coarse_shape,
        "source_window_shape": preview.source_window_shape,
        "display_shape": preview.display_shape,
        "active_pixel_count": preview.active_pixel_count,
        "source_window": preview.source_window,
        "bounds_latlon": preview.bounds_latlon,
        "full_bounds_latlon": preview.full_bounds_latlon,
        "display_range_cm": (round(preview.vmin, 2), round(preview.vmax, 2)),
    }
