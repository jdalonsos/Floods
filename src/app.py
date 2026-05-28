"""Streamlit dashboard for browsing official JRC flood rasters by year."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from flood_preview import (
    build_folium_map,
    create_static_preview_figure,
    discover_flood_raster_files,
    preview_summary,
    read_flood_preview,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = {
    "Raw official archive": PROJECT_ROOT / "data" / "JRC_flood_depth_maps",
    "Filtered working tree": PROJECT_ROOT / "data" / "Filtered",
}
PREVIEW_CACHE_VERSION = "preview-polygon-fallback-v3"


st.set_page_config(page_title="Flood TIFF Explorer", layout="wide")
st.title("Flood TIFF Explorer")
st.caption(
    "Browse official flood rasters by year, then render an efficient preview "
    "without reading the full TIFF at native resolution."
)


@st.cache_data(show_spinner=False)
def load_raster_inventory(root_str: str) -> list[dict]:
    return [record.to_dict() for record in discover_flood_raster_files(root_str)]


@st.cache_data(show_spinner=False, max_entries=12)
def load_preview(
    tif_path: str,
    coarse_max_size: int,
    detail_max_size: int,
    source_padding_pixels: int,
    threshold_cm: float,
    upper_quantile: float,
    preview_cache_version: str,
) -> object:
    # Keep the cache key tied to preview-algorithm changes in helper modules.
    _ = preview_cache_version
    return read_flood_preview(
        tif_path=tif_path,
        coarse_max_size=coarse_max_size,
        detail_max_size=detail_max_size,
        threshold_cm=threshold_cm,
        mask_values=(9999,),
        source_padding_pixels=source_padding_pixels,
        upper_quantile=upper_quantile,
    )


def choose_root() -> Path:
    root_option = st.sidebar.selectbox(
        "Raster source",
        [*DEFAULT_ROOTS.keys(), "Custom path"],
        index=0,
    )
    if root_option == "Custom path":
        custom_root = st.sidebar.text_input(
            "Custom raster directory",
            value=str(DEFAULT_ROOTS["Raw official archive"]),
        )
        return Path(custom_root).expanduser()
    return DEFAULT_ROOTS[root_option]


def main() -> None:
    st.sidebar.header("Controls")
    raster_root = choose_root()

    if not raster_root.exists():
        st.error(f"Raster directory not found: {raster_root}")
        st.stop()

    inventory = load_raster_inventory(str(raster_root))
    if not inventory:
        st.error(
            "No official JRC flood TIFFs were found in this directory. "
            "The dashboard only keeps files that match the official README naming convention."
        )
        st.stop()

    df = pd.DataFrame(inventory).sort_values(
        ["year", "start_date", "end_date", "flood_id", "raster_file"],
        na_position="last",
    )
    available_years = sorted(df["year"].dropna().astype(int).unique().tolist())
    year_counts = df.groupby("year", dropna=False).size().rename("n_rasters").reset_index()

    st.sidebar.metric("Official rasters", f"{len(df):,}")
    st.sidebar.metric("Available years", f"{len(available_years):,}")

    if available_years:
        default_year_index = len(available_years) - 1
        selected_year = st.sidebar.selectbox("Year", available_years, index=default_year_index)
        year_df = df[df["year"] == selected_year].copy()
    else:
        selected_year = None
        year_df = df.copy()

    name_filter = st.sidebar.text_input("Filter filenames", value="")
    if name_filter.strip():
        year_df = year_df[
            year_df["raster_file"].str.contains(name_filter.strip(), case=False, regex=False)
        ].copy()

    if year_df.empty:
        st.warning("No rasters match the current year and filename filter.")
        st.stop()

    file_paths = year_df["path"].tolist()
    label_by_path = {
        row["path"]: (
            f"{row['start_date']} | cluster {int(row['flood_id']):03d} | "
            f"{row['raster_file']}"
        )
        for _, row in year_df.iterrows()
    }
    selected_path = st.sidebar.selectbox(
        "Raster file",
        file_paths,
        format_func=lambda path: label_by_path[path],
    )

    map_mode = st.sidebar.radio(
        "Map rendering",
        options=["auto", "pixels", "raster"],
        format_func=lambda value: {
            "auto": "Auto",
            "pixels": "Polygon pixels",
            "raster": "Raster overlay",
        }[value],
        index=0,
    )
    tiles = st.sidebar.selectbox(
        "Basemap",
        options=["CartoDB positron", "OpenStreetMap"],
        index=0,
    )

    with st.sidebar.expander("Advanced preview settings", expanded=False):
        coarse_max_size = st.slider("Coarse scan max size", 400, 2500, 1200, 100)
        detail_max_size = st.slider("Detailed crop max size", 600, 3200, 1800, 100)
        source_padding_pixels = st.slider("Source padding (pixels)", 0, 2500, 600, 100)
        threshold_cm = st.slider("Flood threshold (cm)", 0.0, 20.0, 0.0, 0.5)
        upper_quantile = st.slider("Upper display quantile", 0.90, 1.00, 0.995, 0.001)
        pixel_mode_max_cells = st.slider(
            "Preview polygon budget",
            250,
            40000,
            20000,
            250,
            help=(
                "Maximum merged preview polygons before the app falls back "
                "to the approximate raster overlay."
            ),
        )
        exact_native_pixel_limit = st.slider(
            "Exact native pixel cap",
            1000,
            100000,
            12000,
            1000,
        )

    selected_row = year_df.loc[year_df["path"] == selected_path].iloc[0].to_dict()

    st.subheader(selected_row["raster_file"])
    st.code(selected_row["path"], language="text")

    metric_cols = st.columns(4)
    year_value = selected_row["year"]
    metric_cols[0].metric(
        "Event year",
        str(int(year_value)) if pd.notna(year_value) else "NA",
    )
    metric_cols[1].metric("Duration (days)", str(int(selected_row["duration_days"])))
    metric_cols[2].metric("GFM extent A0 (km2)", str(int(selected_row["gfm_extent_km2"])))
    metric_cols[3].metric(
        "Enhanced extent A (km2)",
        str(int(selected_row["enhanced_extent_km2"])),
    )

    with st.spinner("Reading efficient flood preview..."):
        preview = load_preview(
            tif_path=selected_path,
            coarse_max_size=coarse_max_size,
            detail_max_size=detail_max_size,
            source_padding_pixels=source_padding_pixels,
            threshold_cm=threshold_cm,
            upper_quantile=upper_quantile,
            preview_cache_version=PREVIEW_CACHE_VERSION,
        )

    preview_info = preview_summary(preview)
    preview_metric_cols = st.columns(4)
    preview_metric_cols[0].metric("Source raster shape", f"{preview.src_width:,} x {preview.src_height:,}")
    preview_metric_cols[1].metric(
        "Detailed crop shape",
        f"{preview.display_shape[1]:,} x {preview.display_shape[0]:,}",
    )
    preview_metric_cols[2].metric("Active preview pixels", f"{preview.active_pixel_count:,}")
    preview_metric_cols[3].metric(
        "Displayed range (cm)",
        f"{preview.vmin:.1f} to {preview.vmax:.1f}",
    )

    tabs = st.tabs(["Interactive map", "Static preview", "Metadata", "Year inventory"])

    with tabs[0]:
        st.write(
            "The map uses the same efficient two-stage logic as the notebook: "
            "coarse whole-raster scan first, then a detailed local crop."
        )
        flood_map = build_folium_map(
            preview,
            cmap_name="turbo",
            tiles=tiles,
            mode=map_mode,
            pixel_mode_max_cells=pixel_mode_max_cells,
            threshold_cm=threshold_cm,
            mask_values=(9999,),
            exact_native_pixel_limit=exact_native_pixel_limit,
        )
        html = flood_map.get_root().render()
        st.download_button(
            "Download current map as HTML",
            data=html.encode("utf-8"),
            file_name=f"{Path(selected_path).stem}_preview.html",
            mime="text/html",
        )
        components.html(html, height=780, scrolling=False)

    with tabs[1]:
        fig = create_static_preview_figure(preview, cmap_name="turbo")
        st.pyplot(fig, width="stretch")
        fig.clear()

    with tabs[2]:
        metadata_rows = {
            "event_id": selected_row["event_id"],
            "start_date": selected_row["start_date"],
            "end_date": selected_row["end_date"],
            "flood_id": int(selected_row["flood_id"]),
            "centroid_lat_deg": float(selected_row["centroid_lat_cents"]) / 100.0,
            "centroid_lon_deg": float(selected_row["centroid_lon_cents"]) / 100.0,
            **preview_info,
        }
        st.json(metadata_rows)

    with tabs[3]:
        st.write("Official raster counts discovered in the selected source tree.")
        st.dataframe(year_counts, width="stretch", hide_index=True)
        st.write("Files currently visible under the selected year and filename filter.")
        table_cols = [
            "start_date",
            "end_date",
            "flood_id",
            "duration_days",
            "gfm_extent_km2",
            "enhanced_extent_km2",
            "raster_file",
        ]
        st.dataframe(year_df[table_cols], width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
