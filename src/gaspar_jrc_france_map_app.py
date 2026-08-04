from __future__ import annotations

import calendar
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from branca.colormap import linear

from france_commune_activity import (
    DEFAULT_ADMINEXPRESS_PATH,
    DEFAULT_FRANCE_LOOKUP_PATH,
    DEFAULT_GASPAR_PROCESSED_PATH,
    DEFAULT_GASPAR_RAW_CSV_PATH,
    DEFAULT_GASPAR_RAW_XLSX_PATH,
    DEFAULT_GASPAR_SHEET,
    DEFAULT_HANZE_EVENTS_PATH,
    DEFAULT_JRC_EVENTS_PATH,
    DEFAULT_OLD_INSEE_UPDATE_PATH,
    aggregate_gaspar_activity,
    aggregate_jrc_activity,
    aggregate_hanze_activity,
    build_comparison_activity,
    build_custom_range_period,
    build_department_boundaries,
    build_france_outline,
    build_month_period,
    build_single_day_period,
    build_year_period,
    filter_records_active_between,
    load_commune_geometries,
    load_france_lookup,
    load_historical_insee_updates,
    prepare_jrc_activity_rows,
    prepare_hanze_activity_rows,
    prepare_processed_gaspar_rows,
    prepare_raw_gaspar_rows,
    resolve_gaspar_current_communes,
)


st.set_page_config(
    page_title="France Flood Source Commune Activity",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MAP_TILES = {
    "CartoDB Positron": "CartoDB Positron",
    "OpenStreetMap": "OpenStreetMap",
}
COMPARISON_COLORS = {
    "both": "#0f766e",
    "gaspar_only": "#ea580c",
    "jrc_only": "#2563eb",
}


def choose_default_raw_gaspar_path() -> Path:
    if DEFAULT_GASPAR_RAW_XLSX_PATH.exists():
        return DEFAULT_GASPAR_RAW_XLSX_PATH
    return DEFAULT_GASPAR_RAW_CSV_PATH


@st.cache_data(show_spinner=False)
def cached_load_lookup(path: str) -> pd.DataFrame:
    return load_france_lookup(path)


@st.cache_data(show_spinner=False)
def cached_load_history(path: str) -> pd.DataFrame:
    return load_historical_insee_updates(path)


@st.cache_data(show_spinner=False)
def cached_prepare_processed_gaspar(
    gaspar_path: str,
    sheet_name: str,
    lookup_path: str,
    history_path: str,
) -> tuple[pd.DataFrame, dict]:
    gaspar_rows, source_diagnostics = prepare_processed_gaspar_rows(gaspar_path, sheet_name=sheet_name)
    resolved_rows, resolution_diagnostics = resolve_gaspar_current_communes(
        gaspar_rows,
        france_lookup=cached_load_lookup(lookup_path),
        historical_updates=cached_load_history(history_path),
    )
    return resolved_rows, {
        "source": source_diagnostics,
        "resolution": resolution_diagnostics,
    }


@st.cache_data(show_spinner=False)
def cached_prepare_raw_gaspar(
    gaspar_path: str,
    lookup_path: str,
    history_path: str,
) -> tuple[pd.DataFrame, dict]:
    gaspar_rows, source_diagnostics = prepare_raw_gaspar_rows(gaspar_path)
    resolved_rows, resolution_diagnostics = resolve_gaspar_current_communes(
        gaspar_rows,
        france_lookup=cached_load_lookup(lookup_path),
        historical_updates=cached_load_history(history_path),
    )
    return resolved_rows, {
        "source": source_diagnostics,
        "resolution": resolution_diagnostics,
    }


@st.cache_data(show_spinner=False)
def cached_prepare_jrc(jrc_path: str) -> tuple[pd.DataFrame, dict]:
    return prepare_jrc_activity_rows(jrc_path)


@st.cache_data(show_spinner=False)
def cached_prepare_hanze(hanze_path: str, lookup_path: str) -> tuple[pd.DataFrame, dict]:
    return prepare_hanze_activity_rows(hanze_path, lookup_path)


@st.cache_resource(show_spinner=False)
def cached_map_layers(
    adminexpress_path: str,
    commune_simplify_tolerance: float,
    department_simplify_tolerance: float,
    outline_simplify_tolerance: float,
):
    base_communes = load_commune_geometries(adminexpress_path, simplify_tolerance=0.0)
    display_communes = base_communes.copy()
    if commune_simplify_tolerance > 0:
        display_communes["geometry"] = display_communes.geometry.simplify(
            commune_simplify_tolerance,
            preserve_topology=True,
        )
    departments = build_department_boundaries(
        base_communes,
        simplify_tolerance=department_simplify_tolerance,
    )
    outline = build_france_outline(
        base_communes,
        simplify_tolerance=outline_simplify_tolerance,
    )
    return display_communes, departments, outline


def metric_options_for_mode(display_mode: str) -> dict[str, str]:
    if display_mode == "Gaspar":
        return {
            "Active rows": "gaspar_row_count",
            "Unique event groups": "gaspar_unique_event_count",
            "Unique decrees": "gaspar_unique_decree_count",
        }
    if display_mode == "JRC":
        return {
            "Active rows": "jrc_row_count",
            "Unique events": "jrc_unique_event_count",
            "Max depth (cm)": "jrc_max_depth_cm",
            "Flooded area (m2)": "jrc_total_flooded_area_m2",
        }
    if display_mode == "HANZE":
        return {
            "Active rows": "hanze_row_count",
            "Unique events": "hanze_unique_event_count",
        }
    return {"Comparison status": "comparison_class"}


def coerce_map_value(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.fillna(0.0)


def prepare_tooltip_columns(activity: pd.DataFrame, display_mode: str) -> pd.DataFrame:
    tooltip_df = activity.copy()
    if "gaspar_row_count" in tooltip_df.columns:
        tooltip_df["gaspar_row_count"] = coerce_map_value(tooltip_df["gaspar_row_count"]).astype(int)
    if "gaspar_unique_event_count" in tooltip_df.columns:
        tooltip_df["gaspar_unique_event_count"] = coerce_map_value(
            tooltip_df["gaspar_unique_event_count"]
        ).astype(int)
    if "gaspar_unique_decree_count" in tooltip_df.columns:
        tooltip_df["gaspar_unique_decree_count"] = coerce_map_value(
            tooltip_df["gaspar_unique_decree_count"]
        ).astype(int)
    if "jrc_row_count" in tooltip_df.columns:
        tooltip_df["jrc_row_count"] = coerce_map_value(tooltip_df["jrc_row_count"]).astype(int)
    if "jrc_unique_event_count" in tooltip_df.columns:
        tooltip_df["jrc_unique_event_count"] = coerce_map_value(
            tooltip_df["jrc_unique_event_count"]
        ).astype(int)
    if "jrc_total_flooded_area_m2" in tooltip_df.columns:
        tooltip_df["jrc_total_flooded_area_m2"] = coerce_map_value(
            tooltip_df["jrc_total_flooded_area_m2"]
        ).round(0)
    if "jrc_max_depth_cm" in tooltip_df.columns:
        tooltip_df["jrc_max_depth_cm"] = coerce_map_value(tooltip_df["jrc_max_depth_cm"]).round(1)
    for column in ["hanze_row_count", "hanze_unique_event_count"]:
        if column in tooltip_df.columns:
            tooltip_df[column] = coerce_map_value(tooltip_df[column]).astype(int)
    if display_mode == "Comparison" and "comparison_class" in tooltip_df.columns:
        tooltip_df["comparison_label"] = tooltip_df["comparison_class"].map(
            {
                "both": "Both active",
                "gaspar_only": "Gaspar only",
                "jrc_only": "JRC only",
            }
        ).fillna("Inactive")
    return tooltip_df


def build_tooltip_config(display_mode: str) -> tuple[list[str], list[str]]:
    if display_mode == "Gaspar":
        return (
            [
                "commune_name_current",
                "insee_com",
                "lau_code_local",
                "gaspar_row_count",
                "gaspar_unique_event_count",
                "gaspar_unique_decree_count",
                "gaspar_risk_labels",
                "gaspar_match_methods",
            ],
            [
                "Commune",
                "Current INSEE",
                "LAU / local code",
                "Active Gaspar rows",
                "Unique Gaspar event groups",
                "Unique decrees",
                "Risk labels",
                "Commune match methods",
            ],
        )
    if display_mode == "JRC":
        return (
            [
                "commune_name_current",
                "insee_com",
                "lau_code_local",
                "jrc_row_count",
                "jrc_unique_event_count",
                "jrc_max_depth_cm",
                "jrc_total_flooded_area_m2",
            ],
            [
                "Commune",
                "Current INSEE",
                "LAU / local code",
                "Active JRC rows",
                "Unique JRC events",
                "Max depth (cm)",
                "Flooded area (m2)",
            ],
        )
    if display_mode == "HANZE":
        return (
            ["commune_name_current", "insee_com", "nuts3_code", "nuts3_name", "hanze_row_count", "hanze_unique_event_count", "hanze_flood_types", "hanze_flood_sources", "hanze_causes"],
            ["Commune", "Current INSEE", "NUTS3", "NUTS3 name", "Active HANZE rows", "Unique HANZE events", "Flood types", "Flood sources", "Causes"],
        )
    return (
        [
            "commune_name_current",
            "insee_com",
            "lau_code_local",
            "gaspar_row_count",
            "gaspar_unique_event_count",
            "jrc_row_count",
            "jrc_unique_event_count",
            "jrc_max_depth_cm",
            "comparison_label",
        ],
        [
            "Commune",
            "Current INSEE",
            "LAU / local code",
            "Gaspar active rows",
            "Gaspar unique event groups",
            "JRC active rows",
            "JRC unique events",
            "JRC max depth (cm)",
            "Status",
        ],
    )


def build_map(
    *,
    activity_gdf,
    display_mode: str,
    metric_column: str,
    period_label: str,
    tiles: str,
    show_departments: bool,
    outline_gdf,
    departments_gdf,
):
    fmap = folium.Map(
        location=[46.6, 2.4],
        zoom_start=5.6,
        tiles=tiles,
        control_scale=True,
    )

    folium.GeoJson(
        outline_gdf.to_json(),
        name="France outline",
        style_function=lambda _feature: {
            "color": "#111827",
            "weight": 1.3,
            "fillColor": "#f8fafc",
            "fillOpacity": 0.05,
        },
    ).add_to(fmap)

    if show_departments:
        folium.GeoJson(
            departments_gdf.to_json(),
            name="Departments",
            style_function=lambda _feature: {
                "color": "#94a3b8",
                "weight": 0.5,
                "fillOpacity": 0.0,
            },
        ).add_to(fmap)

    if activity_gdf.empty:
        folium.LayerControl(collapsed=False).add_to(fmap)
        return fmap

    tooltip_fields, tooltip_aliases = build_tooltip_config(display_mode)
    tooltip_pairs = [
        (field, alias)
        for field, alias in zip(tooltip_fields, tooltip_aliases, strict=False)
        if field in activity_gdf.columns
    ]
    tooltip_fields = [field for field, _alias in tooltip_pairs]
    tooltip_aliases = [alias for _field, alias in tooltip_pairs]

    if display_mode == "Comparison":
        styled = activity_gdf.copy()
        styled["_fill_color"] = styled["comparison_class"].map(COMPARISON_COLORS).fillna("#cbd5e1")
        folium.GeoJson(
            styled.to_json(),
            name=f"Active communes ({period_label})",
            style_function=lambda feature: {
                "color": "#334155",
                "weight": 0.35,
                "fillColor": feature["properties"]["_fill_color"],
                "fillOpacity": 0.85,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                localize=True,
                sticky=False,
                labels=True,
            ),
        ).add_to(fmap)
        legend_html = """
        <div style="
            position: fixed;
            bottom: 18px;
            left: 18px;
            z-index: 9999;
            background: white;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font-size: 13px;
            line-height: 1.5;
        ">
            <div style="font-weight: 600; margin-bottom: 4px;">Comparison</div>
            <div><span style="display:inline-block;width:12px;height:12px;background:#0f766e;margin-right:8px;"></span>Both active</div>
            <div><span style="display:inline-block;width:12px;height:12px;background:#ea580c;margin-right:8px;"></span>Gaspar only</div>
            <div><span style="display:inline-block;width:12px;height:12px;background:#2563eb;margin-right:8px;"></span>JRC only</div>
        </div>
        """
        fmap.get_root().html.add_child(folium.Element(legend_html))
        folium.LayerControl(collapsed=False).add_to(fmap)
        return fmap

    styled = activity_gdf.copy()
    styled[metric_column] = coerce_map_value(styled[metric_column])
    vmax = float(styled[metric_column].max())
    color_scale = linear.YlOrRd_09.scale(0.0, max(vmax, 1.0))
    color_scale.caption = f"{display_mode} metric: {metric_column}"
    styled["_fill_color"] = styled[metric_column].map(color_scale)

    folium.GeoJson(
        styled.to_json(),
        name=f"Active communes ({period_label})",
        style_function=lambda feature: {
            "color": "#334155",
            "weight": 0.35,
            "fillColor": feature["properties"]["_fill_color"],
            "fillOpacity": 0.85,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
            sticky=False,
            labels=True,
        ),
    ).add_to(fmap)
    color_scale.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap


def build_period_selector(years: list[int]):
    st.sidebar.subheader("Time filter")
    period_mode = st.sidebar.selectbox(
        "Period mode",
        options=["Specific date", "Month", "Year", "Custom range"],
        index=1,
    )

    if period_mode == "Specific date":
        default_day = pd.Timestamp(year=max(years), month=1, day=15).date()
        selected_day = st.sidebar.date_input("Date", value=default_day)
        return build_single_day_period(selected_day)

    if period_mode == "Month":
        selected_year = st.sidebar.selectbox("Year", years, index=len(years) - 1)
        month_options = list(range(1, 13))
        selected_month = st.sidebar.selectbox(
            "Month",
            options=month_options,
            index=0,
            format_func=lambda month: f"{month:02d} - {calendar.month_name[month]}",
        )
        return build_month_period(selected_year, selected_month)

    if period_mode == "Year":
        selected_year = st.sidebar.selectbox("Year", years, index=len(years) - 1)
        return build_year_period(selected_year)

    default_start = pd.Timestamp(year=min(years), month=1, day=1).date()
    default_end = pd.Timestamp(year=max(years), month=12, day=31).date()
    start_date = st.sidebar.date_input("Start date", value=default_start)
    end_date = st.sidebar.date_input("End date", value=default_end)
    return build_custom_range_period(start_date, end_date)


def main() -> None:
    st.title("France Flood Source Commune Activity")
    st.caption(
        "Visualize active French communes for a month, year, exact date, or custom period, "
        "using Gaspar, JRC, HANZE, or the Gaspar/JRC comparison on the same France map."
    )

    st.sidebar.header("Sources")
    gaspar_variant = st.sidebar.selectbox(
        "Gaspar input",
        options=["Processed workbook", "Raw dataset (live transform)"],
        index=0,
    )
    display_mode = st.sidebar.selectbox(
        "Display mode",
        #options=["Gaspar", "JRC", "HANZE", "Comparison"],
        options=["Gaspar", "JRC", "Comparison"],
        index=2,
    )

    processed_gaspar_path = st.sidebar.text_input(
        "Processed Gaspar path",
        value=str(DEFAULT_GASPAR_PROCESSED_PATH),
    )
    raw_gaspar_path = st.sidebar.text_input(
        "Raw Gaspar path",
        value=str(choose_default_raw_gaspar_path()),
    )
    gaspar_sheet_name = st.sidebar.text_input(
        "Processed Gaspar sheet",
        value=DEFAULT_GASPAR_SHEET,
    )
    jrc_path = st.sidebar.text_input(
        "JRC France commune-event path",
        value=str(DEFAULT_JRC_EVENTS_PATH),
    )
    #hanze_path = st.sidebar.text_input(
    #    "HANZE transformed events path",
    #    value=str(DEFAULT_HANZE_EVENTS_PATH),
    #)
    lookup_path = st.sidebar.text_input(
        "France LAU / INSEE lookup path",
        value=str(DEFAULT_FRANCE_LOOKUP_PATH),
    )
    history_path = st.sidebar.text_input(
        "Old INSEE update path",
        value=str(DEFAULT_OLD_INSEE_UPDATE_PATH),
    )
    adminexpress_path = st.sidebar.text_input(
        "AdminExpress commune geometry path",
        value=str(DEFAULT_ADMINEXPRESS_PATH),
    )

    gaspar_rows = None
    gaspar_diagnostics = None
    if display_mode in {"Gaspar", "Comparison"}:
        with st.spinner("Loading Gaspar rows and resolving current communes..."):
            if gaspar_variant == "Processed workbook":
                gaspar_rows, gaspar_diagnostics = cached_prepare_processed_gaspar(
                    processed_gaspar_path,
                    gaspar_sheet_name,
                    lookup_path,
                    history_path,
                )
            else:
                gaspar_rows, gaspar_diagnostics = cached_prepare_raw_gaspar(
                    raw_gaspar_path,
                    lookup_path,
                    history_path,
                )

    jrc_rows = None
    jrc_diagnostics = None
    if display_mode in {"JRC", "Comparison"}:
        with st.spinner("Loading JRC commune-event rows..."):
            jrc_rows, jrc_diagnostics = cached_prepare_jrc(jrc_path)

    hanze_rows = None
    hanze_diagnostics = None
    #if display_mode == "HANZE":
    #    with st.spinner("Loading HANZE NUTS3 events and mapping them to communes..."):
            #hanze_rows, hanze_diagnostics = cached_prepare_hanze(hanze_path, lookup_path)

    date_frames: list[pd.DataFrame] = []
    if gaspar_rows is not None:
        date_frames.append(gaspar_rows[["activity_start_date", "activity_end_date"]])
    if jrc_rows is not None:
        date_frames.append(jrc_rows[["activity_start_date", "activity_end_date"]])
    if hanze_rows is not None:
        date_frames.append(hanze_rows[["activity_start_date", "activity_end_date"]])
    if not date_frames:
        st.error("No source rows were loaded.")
        st.stop()

    min_year = min(
        int(frame["activity_start_date"].min().year)
        for frame in date_frames
        if frame["activity_start_date"].notna().any()
    )
    max_year = max(
        int(frame["activity_end_date"].max().year)
        for frame in date_frames
        if frame["activity_end_date"].notna().any()
    )
    years = list(range(min_year, max_year + 1))
    selected_period = build_period_selector(years)

    st.sidebar.subheader("Map rendering")
    metric_options = metric_options_for_mode(display_mode)
    metric_label = st.sidebar.selectbox("Metric", list(metric_options.keys()), index=0)
    metric_column = metric_options[metric_label]
    tiles_label = st.sidebar.selectbox("Basemap", list(MAP_TILES.keys()), index=0)
    show_departments = st.sidebar.checkbox("Show department boundaries", value=True)
    commune_simplify_tolerance = st.sidebar.slider(
        "Commune simplify tolerance",
        min_value=0.0,
        max_value=0.01,
        value=0.001,
        step=0.0005,
        help="Higher values make the map lighter and faster but less detailed.",
    )

    with st.spinner("Loading France commune geometries..."):
        communes_gdf, departments_gdf, outline_gdf = cached_map_layers(
            adminexpress_path,
            commune_simplify_tolerance,
            max(commune_simplify_tolerance * 2.5, 0.004),
            max(commune_simplify_tolerance * 4.0, 0.008),
        )

    gaspar_active_all = None
    gaspar_active = None
    jrc_active = None
    hanze_active = None
    activity = None
    filtered_row_tables: dict[str, pd.DataFrame] = {}

    if gaspar_rows is not None:
        gaspar_active_all = filter_records_active_between(
            gaspar_rows,
            start_col="activity_start_date",
            end_col="activity_end_date",
            period_start=selected_period.start_date,
            period_end=selected_period.end_date,
        )
        gaspar_active = gaspar_active_all[
            gaspar_active_all["gaspar_commune_match_found"].fillna(False)
        ].copy()
        filtered_row_tables["Gaspar rows"] = gaspar_active_all

    if jrc_rows is not None:
        jrc_active = filter_records_active_between(
            jrc_rows,
            start_col="activity_start_date",
            end_col="activity_end_date",
            period_start=selected_period.start_date,
            period_end=selected_period.end_date,
        )
        filtered_row_tables["JRC rows"] = jrc_active

    if hanze_rows is not None:
        hanze_active = filter_records_active_between(
            hanze_rows,
            start_col="activity_start_date",
            end_col="activity_end_date",
            period_start=selected_period.start_date,
            period_end=selected_period.end_date,
        )
        filtered_row_tables["HANZE rows"] = hanze_active

    if display_mode == "Gaspar":
        activity = aggregate_gaspar_activity(gaspar_active)
    elif display_mode == "JRC":
        activity = aggregate_jrc_activity(jrc_active)
    elif display_mode == "HANZE":
        activity = aggregate_hanze_activity(hanze_active)
    else:
        activity = build_comparison_activity(gaspar_active, jrc_active)
        activity = activity[activity["comparison_class"].isin(["both", "gaspar_only", "jrc_only"])].copy()

    activity = prepare_tooltip_columns(activity, display_mode)
    activity_gdf = communes_gdf.merge(activity, on="insee_com", how="inner", validate="1:1")

    st.subheader(f"Active communes for {selected_period.label}")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Active communes", f"{len(activity):,}")
    if display_mode == "Comparison":
        metric_cols[1].metric(
            "Filtered Gaspar rows",
            f"{len(gaspar_active_all) if gaspar_active_all is not None else 0:,}",
        )
        metric_cols[2].metric(
            "Filtered JRC rows",
            f"{len(jrc_active) if jrc_active is not None else 0:,}",
        )
        both_count = int(activity["comparison_class"].eq("both").sum()) if not activity.empty else 0
        metric_cols[3].metric(
            "Both / Gaspar only / JRC only",
            f"{both_count:,} / {int(activity['comparison_class'].eq('gaspar_only').sum()):,} / "
            f"{int(activity['comparison_class'].eq('jrc_only').sum()):,}",
        )
    elif gaspar_active is not None:
        metric_cols[1].metric(
            "Filtered Gaspar rows",
            f"{len(gaspar_active_all) if gaspar_active_all is not None else 0:,}",
        )
        metric_cols[2].metric("Matched Gaspar rows", f"{len(gaspar_active):,}")
        metric_cols[3].metric(
            "Unresolved filtered Gaspar rows",
            f"{len(gaspar_active_all) - len(gaspar_active) if gaspar_active_all is not None else 0:,}",
        )
    elif jrc_active is not None:
        metric_cols[1].metric("Filtered JRC rows", f"{len(jrc_active):,}")
        unique_events = int(jrc_active["jrc_event_id"].nunique()) if jrc_active is not None else 0
        metric_cols[2].metric("Active JRC events", f"{unique_events:,}")
        metric_cols[3].metric(
            "Active JRC communes with depth",
            f"{int(activity['jrc_max_depth_cm'].fillna(0).gt(0).sum()) if not activity.empty else 0:,}",
        )
    elif hanze_active is not None:
        metric_cols[1].metric("Filtered HANZE rows", f"{len(hanze_active):,}")
        metric_cols[2].metric("Active HANZE events", f"{hanze_active['hanze_event_id'].nunique():,}")
        metric_cols[3].metric("Active NUTS3 regions", f"{hanze_active['nuts3_code'].nunique():,}")
    else:
        metric_cols[1].metric("Filtered rows", "0")
        metric_cols[2].metric("Source metric", "0")
        metric_cols[3].metric("Resolved rows", "0")

    tabs = st.tabs(["Map", "Aggregated table", "Filtered rows", "Diagnostics"])

    with tabs[0]:
        if activity_gdf.empty:
            st.warning("No commune is active for the selected period and source filters.")
        france_map = build_map(
            activity_gdf=activity_gdf,
            display_mode=display_mode,
            metric_column=metric_column,
            period_label=selected_period.label,
            tiles=MAP_TILES[tiles_label],
            show_departments=show_departments,
            outline_gdf=outline_gdf,
            departments_gdf=departments_gdf,
        )
        html = france_map.get_root().render()
        st.download_button(
            "Download current aggregated table as CSV",
            data=activity.sort_values("insee_com").to_csv(index=False).encode("utf-8-sig"),
            file_name=f"france_commune_activity_{display_mode.lower()}_{selected_period.label.replace(' ', '_').replace(':', '_')}.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download current map as HTML",
            data=html.encode("utf-8"),
            file_name=f"france_commune_activity_{display_mode.lower()}_{selected_period.label.replace(' ', '_').replace(':', '_')}.html",
            mime="text/html",
        )
        components.html(html, height=780, scrolling=False)

    with tabs[1]:
        sort_column = metric_column if metric_column in activity.columns else "insee_com"
        display_table = activity.sort_values(sort_column, ascending=False, kind="stable")
        st.dataframe(display_table, width="stretch", hide_index=True)

    with tabs[2]:
        if not filtered_row_tables:
            st.info("No filtered source rows to show.")
        else:
            row_tabs = st.tabs(list(filtered_row_tables.keys()))
            for tab, table_name in zip(row_tabs, filtered_row_tables.keys(), strict=False):
                with tab:
                    row_df = filtered_row_tables[table_name]
                    st.dataframe(row_df, width="stretch", hide_index=True)

    with tabs[3]:
        if gaspar_diagnostics is not None:
            st.markdown("**Gaspar diagnostics**")
            st.json(gaspar_diagnostics)
        if jrc_diagnostics is not None:
            st.markdown("**JRC diagnostics**")
            st.json(jrc_diagnostics)
        if hanze_diagnostics is not None:
            st.markdown("**HANZE diagnostics**")
            st.json(hanze_diagnostics)
        st.markdown("**Map inputs**")
        st.json(
            {
                "display_mode": display_mode,
                "gaspar_variant": gaspar_variant if gaspar_rows is not None else None,
                "selected_period": {
                    "start_date": str(selected_period.start_date.date()),
                    "end_date": str(selected_period.end_date.date()),
                    "label": selected_period.label,
                },
                "active_communes_rendered": int(len(activity_gdf)),
                "geometry_path": adminexpress_path,
                "lookup_path": lookup_path,
            }
        )


if __name__ == "__main__":
    main()
