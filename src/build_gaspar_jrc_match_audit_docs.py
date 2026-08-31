from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from textwrap import dedent

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from france_commune_activity import (
    DEFAULT_ADMINEXPRESS_PATH,
    DEFAULT_FRANCE_LOOKUP_PATH,
    DEFAULT_GASPAR_PROCESSED_PATH,
    DEFAULT_JRC_EVENTS_PATH,
    DEFAULT_OLD_INSEE_UPDATE_PATH,
    build_comparison_activity,
    filter_records_active_between,
    load_commune_geometries,
    load_france_lookup,
    load_historical_insee_updates,
    prepare_jrc_activity_rows,
    prepare_processed_gaspar_rows,
    resolve_gaspar_current_communes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "gaspar_jrc_match_audit"
SUMMARY_7D_DIR = PROJECT_ROOT / "data" / "processed" / "jrc_gaspar_comparison_flexible_7d"
SUMMARY_30D_DIR = PROJECT_ROOT / "data" / "processed" / "jrc_gaspar_comparison_flexible_30d"


REGION_NAMES = {
    "11": "Ile-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comte",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhone-Alpes",
    "93": "Provence-Alpes-Cote d'Azur",
    "94": "Corse",
}

STATUS_COLORS = {
    "both": "#0f766e",
    "gaspar_only": "#ea580c",
    "jrc_only": "#2563eb",
}


@dataclass(frozen=True)
class ManualExample:
    slug: str
    title_en: str
    title_fr: str
    region_code: str
    year: int
    quarter: int
    quarter_start: str
    quarter_end: str
    rationale_en: str
    rationale_fr: str
    evidence_links: list[tuple[str, str]]


def read_metric_summary(comparison_dir: Path) -> dict[str, float]:
    summary = pd.read_csv(comparison_dir / "comparison_summary.csv")
    mapping: dict[str, float] = {}
    for _, row in summary.iterrows():
        metric = str(row["metric"])
        value = row["value"]
        try:
            mapping[metric] = float(value)
        except (TypeError, ValueError):
            mapping[metric] = value
    return mapping


def read_coverage(comparison_dir: Path) -> pd.DataFrame:
    return pd.read_csv(comparison_dir / "coverage_overview.csv")


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def int_str(value: float | int) -> str:
    return f"{int(round(float(value))):,}"


def quarter_period(year: int, quarter: int) -> tuple[pd.Timestamp, pd.Timestamp, str]:
    start_month = 1 + (quarter - 1) * 3
    start = pd.Timestamp(year=year, month=start_month, day=1)
    end = start + pd.offsets.QuarterEnd(startingMonth=start_month + 2)
    return start.normalize(), end.normalize(), f"{year}-Q{quarter}"


def load_activity_sources() -> tuple[pd.DataFrame, pd.DataFrame, gpd.GeoDataFrame]:
    lookup = load_france_lookup(DEFAULT_FRANCE_LOOKUP_PATH)
    history = load_historical_insee_updates(DEFAULT_OLD_INSEE_UPDATE_PATH)

    gaspar_rows, _ = prepare_processed_gaspar_rows(DEFAULT_GASPAR_PROCESSED_PATH)
    gaspar_rows, _ = resolve_gaspar_current_communes(
        gaspar_rows,
        france_lookup=lookup,
        historical_updates=history,
    )
    gaspar_rows = gaspar_rows[gaspar_rows["gaspar_commune_match_found"].fillna(False)].copy()

    jrc_rows, _ = prepare_jrc_activity_rows(DEFAULT_JRC_EVENTS_PATH)

    communes = load_commune_geometries(DEFAULT_ADMINEXPRESS_PATH, simplify_tolerance=0.0)
    return gaspar_rows, jrc_rows, communes


def build_example_activity(
    *,
    gaspar_rows: pd.DataFrame,
    jrc_rows: pd.DataFrame,
    communes: gpd.GeoDataFrame,
    region_code: str,
    year: int,
    quarter: int,
) -> tuple[gpd.GeoDataFrame, dict[str, int], pd.DataFrame]:
    start, end, _ = quarter_period(year, quarter)
    gaspar_active = filter_records_active_between(
        gaspar_rows,
        start_col="activity_start_date",
        end_col="activity_end_date",
        period_start=start,
        period_end=end,
    )
    jrc_active = filter_records_active_between(
        jrc_rows,
        start_col="activity_start_date",
        end_col="activity_end_date",
        period_start=start,
        period_end=end,
    )

    activity = build_comparison_activity(gaspar_active, jrc_active)
    commune_ref = communes[
        ["insee_com", "commune_name_current", "insee_dep", "insee_reg", "geometry"]
    ].drop_duplicates(subset=["insee_com"])
    activity_gdf = commune_ref.merge(activity, on="insee_com", how="left", suffixes=("_geom", ""))
    activity_gdf["region_code"] = (
        activity_gdf["insee_reg"].astype("string").combine_first(activity_gdf["insee_reg_geom"].astype("string"))
    )
    activity_gdf["department_code"] = (
        activity_gdf["insee_dep"].astype("string").combine_first(activity_gdf["insee_dep_geom"].astype("string"))
    )
    region_gdf = activity_gdf[activity_gdf["region_code"].eq(region_code)].copy()
    region_gdf["comparison_class"] = region_gdf["comparison_class"].fillna("inactive")

    active_region = region_gdf[region_gdf["comparison_class"].isin(["both", "gaspar_only", "jrc_only"])].copy()
    counts = {
        "active_communes": int(len(active_region)),
        "both": int(active_region["comparison_class"].eq("both").sum()),
        "gaspar_only": int(active_region["comparison_class"].eq("gaspar_only").sum()),
        "jrc_only": int(active_region["comparison_class"].eq("jrc_only").sum()),
    }

    dept_breakdown = (
        active_region.groupby(["department_code", "comparison_class"], dropna=False)
        .size()
        .rename("communes")
        .reset_index()
    )
    return region_gdf, counts, dept_breakdown


def save_example_map(
    *,
    region_gdf: gpd.GeoDataFrame,
    counts: dict[str, int],
    title: str,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.5))
    base = region_gdf.copy()
    active = base[base["comparison_class"].isin(["both", "gaspar_only", "jrc_only"])].copy()
    department_lines = base[["insee_dep", "geometry"]].dissolve(by="insee_dep", as_index=False)

    panels = [
        ("Gaspar active communes", active[active["comparison_class"].isin(["both", "gaspar_only"])], "#ea580c"),
        ("JRC active communes", active[active["comparison_class"].isin(["both", "jrc_only"])], "#2563eb"),
        ("Comparison status", active, None),
    ]

    for ax, (panel_title, subset, color) in zip(axes, panels, strict=True):
        base.plot(ax=ax, color="#f8fafc", edgecolor="#d1d5db", linewidth=0.25)
        if color is not None:
            subset.plot(ax=ax, color=color, edgecolor="#0f172a", linewidth=0.15)
        else:
            for status, status_color in STATUS_COLORS.items():
                class_subset = subset[subset["comparison_class"].eq(status)]
                if not class_subset.empty:
                    class_subset.plot(
                        ax=ax,
                        color=status_color,
                        edgecolor="#0f172a",
                        linewidth=0.15,
                    )
        department_lines.boundary.plot(ax=ax, color="#475569", linewidth=0.35)
        ax.set_title(panel_title, fontsize=11)
        ax.set_axis_off()

    fig.suptitle(
        (
            f"{title}\n"
            f"Active communes: {counts['active_communes']:,} | "
            f"Both: {counts['both']:,} | "
            f"Gaspar only: {counts['gaspar_only']:,} | "
            f"JRC only: {counts['jrc_only']:,}"
        ),
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def top_departments_text(dept_breakdown: pd.DataFrame, status: str, *, limit: int = 4) -> str:
    subset = dept_breakdown[dept_breakdown["comparison_class"].eq(status)].copy()
    if subset.empty:
        return "none"
    subset = subset.sort_values(["communes", "department_code"], ascending=[False, True], kind="stable").head(limit)
    parts = [f"{row.department_code} ({int(row.communes)})" for row in subset.itertuples()]
    return ", ".join(parts)


def build_manual_examples() -> list[ManualExample]:
    return [
        ManualExample(
            slug="grand_est_2021_q3",
            title_en="Grand Est, Q3 2021",
            title_fr="Grand Est, T3 2021",
            region_code="44",
            year=2021,
            quarter=3,
            quarter_start="2021-07-01",
            quarter_end="2021-09-30",
            rationale_en=(
                "This is a July 2021 heavy-impact example with substantial communes in all three classes. "
                "It is useful for checking whether the mismatch is a pure data error or a real difference in "
                "how the two sources represent the same flood episode."
            ),
            rationale_fr=(
                "Il s'agit d'un exemple a fort impact en juillet 2021, avec de nombreuses communes dans les "
                "trois classes. C'est utile pour verifier si le mismatch vient d'une erreur de donnees ou d'une "
                "vraie difference de representation du meme episode de crue."
            ),
            evidence_links=[
                ("L'Est Republicain, Bar-le-Duc under water, 15 July 2021", "https://www.estrepublicain.fr/faits-divers-justice/2021/07/15/inondations-spectaculaires-a-bar-le-duc-la-ville-toute-une-journee-les-pieds-dans-l-eau"),
                ("Meuse prefecture, July 13-15 2021 flood procedure", "https://www.meuse.gouv.fr/Politiques-publiques/Securite/Demande-de-catastrophes-naturelles-Inondations-du-13-au-15-juillet-2021"),
                ("Champagne FM, Asfeld pumping operations, 14 July 2021", "https://www.champagnefm.com/news/a-deborde-56670"),
                ("Radio 8 Ardennes, flood situation update, 16 July 2021", "https://radio8fm.com/infos/article/16614-Pluie_inondations_Point_de_situation_dans_les_Ardennes_ce_16_juillet_2021_a_19h00"),
                ("Reperes de crues, Vieux-les-Asfeld", "https://www.reperesdecrues.developpement-durable.gouv.fr/site/sortie-du-village-en-direction-de-avaux"),
            ],
        ),
        ManualExample(
            slug="bourgogne_franche_comte_2021_q3",
            title_en="Bourgogne-Franche-Comte, Q3 2021",
            title_fr="Bourgogne-Franche-Comte, T3 2021",
            region_code="27",
            year=2021,
            quarter=3,
            quarter_start="2021-07-01",
            quarter_end="2021-09-30",
            rationale_en=(
                "This neighboring July 2021 example is strongly JRC-dominant, but still contains Gaspar-only pockets. "
                "It is useful because the public evidence already shows flood impacts both in the Jura side and in the "
                "Haute-Saone side."
            ),
            rationale_fr=(
                "Cet exemple voisin de juillet 2021 est fortement domine par JRC, tout en gardant des poches "
                "Gaspar-only. Il est utile car les sources publiques montrent deja des impacts de crue a la fois "
                "du cote du Jura et du cote de la Haute-Saone."
            ),
            evidence_links=[
                ("Le Progres, Jura floods, 16 July 2021", "https://www.leprogres.fr/environnement/2021/07/16/inondations-glissement-de-terrain-le-departement-prend-l-eau"),
                ("Le Progres, Jura floods, 17 July 2021", "https://www.leprogres.fr/environnement/2021/07/17/inondations-trois-cents-appels-en-une-heure-trente"),
                ("Official Rhone-Mediterranee basin event report", "https://www.auvergne-rhone-alpes.developpement-durable.gouv.fr/IMG/pdf/20240606-epri-bassinrm-receuil_evts.pdf"),
                ("Legifrance decree of 23 July 2021", "https://www.legifrance.gouv.fr/jorf/id/JORFSCTA000043879099"),
                ("L'Est Republicain, Autet cleanup, 25 July 2021", "https://www.estrepublicain.fr/environnement/2021/07/25/nettoyage-apres-l-invasion-d-eau"),
            ],
        ),
        ManualExample(
            slug="centre_val_de_loire_2016_q2",
            title_en="Centre-Val de Loire, Q2 2016",
            title_fr="Centre-Val de Loire, T2 2016",
            region_code="24",
            year=2016,
            quarter=2,
            quarter_start="2016-04-01",
            quarter_end="2016-06-30",
            rationale_en=(
                "This is a Gaspar-dominant case linked to the major late-May and early-June 2016 floods. "
                "It is a useful counter-example because it shows that some very large recognized events still "
                "produce weak JRC matching at commune level."
            ),
            rationale_fr=(
                "C'est un cas domine par Gaspar, lie aux grandes inondations de fin mai et debut juin 2016. "
                "C'est un contre-exemple utile car il montre que certains evenements officiellement reconnus a "
                "grande echelle gardent un match JRC faible au niveau communal."
            ),
            evidence_links=[
                ("Centre-Val de Loire prefecture, regional floods page", "https://www.prefectures-regions.gouv.fr/centre-val-de-loire/Actualites/Principales/Inondations-en-region-Centre-Val-de-Loire"),
                ("DREAL Centre-Val de Loire, return on late May / early June 2016 floods", "https://www.centre-val-de-loire.developpement-durable.gouv.fr/retour-sur-les-crues-de-fin-mai-et-debut-juin-2016-a3155.html"),
                ("Ministry of the Interior, return-experience report on May-June 2016 floods", "https://www.interieur.gouv.fr/documentation/rapports/inondations-de-mai-et-juin-2016-dans-bassins-moyens-de-seine-et-de-loire-retour-dexperience-16080-r.html"),
                ("Loiret department, remembrance page for May-June 2016 floods", "https://www.loiret.fr/actualite/inondations-de-mai-juin-2016-le-loiret-se-souvient"),
            ],
        ),
    ]


def build_statistics_markdown_en(summary7: dict[str, float], summary30: dict[str, float], coverage7: pd.DataFrame, coverage30: pd.DataFrame) -> str:
    event7 = coverage7[(coverage7["level"] == "commune") & (coverage7["measurement"] == "unique_events")].iloc[0]
    event30 = coverage30[(coverage30["level"] == "commune") & (coverage30["measurement"] == "unique_events")].iloc[0]
    dept7 = coverage7[(coverage7["level"] == "department") & (coverage7["measurement"] == "unique_events")].iloc[0]
    dept30 = coverage30[(coverage30["level"] == "department") & (coverage30["measurement"] == "unique_events")].iloc[0]
    row7 = coverage7[(coverage7["level"] == "commune") & (coverage7["measurement"] == "canonical_rows")].iloc[0]
    row30 = coverage30[(coverage30["level"] == "commune") & (coverage30["measurement"] == "canonical_rows")].iloc[0]

    return dedent(
        f"""
        ## 1. Overall Match Statistics

        The headline event-level comparison already exists in the project output folders:

        - `data/processed/jrc_gaspar_comparison_flexible_7d`
        - `data/processed/jrc_gaspar_comparison_flexible_30d`

        The event grain comes from the comparison code in [src/compare_france_jrc_gaspar_flexible.py](/D:/M2_MoSEF/DataCollection/src/compare_france_jrc_gaspar_flexible.py):

        - `JRC event` = one `jrc_event_id`
        - `Gaspar event` = one `gaspar_event_uid = cod_nat_catnat + dat_deb + dat_fin`

        Important note: this means the Gaspar "event" count is a recognition-period proxy, not a perfect reconstruction of physical disaster episodes.

        ### National event-level coverage, commune matching rule

        | Window | JRC matched | JRC exclusive | JRC total | JRC match rate | Gaspar matched | Gaspar exclusive | Gaspar total | Gaspar match rate |
        | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
        | 7 days | {int_str(event7.jrc_matched)} | {int_str(event7.jrc_total - event7.jrc_matched)} | {int_str(event7.jrc_total)} | {pct(event7.jrc_match_share)} | {int_str(event7.gaspar_matched)} | {int_str(event7.gaspar_total - event7.gaspar_matched)} | {int_str(event7.gaspar_total)} | {pct(event7.gaspar_match_share)} |
        | 30 days | {int_str(event30.jrc_matched)} | {int_str(event30.jrc_total - event30.jrc_matched)} | {int_str(event30.jrc_total)} | {pct(event30.jrc_match_share)} | {int_str(event30.gaspar_matched)} | {int_str(event30.gaspar_total - event30.gaspar_matched)} | {int_str(event30.gaspar_total)} | {pct(event30.gaspar_match_share)} |

        ### National event-level coverage, department matching rule

        | Window | JRC matched | JRC exclusive | JRC total | JRC match rate | Gaspar matched | Gaspar exclusive | Gaspar total | Gaspar match rate |
        | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
        | 7 days | {int_str(dept7.jrc_matched)} | {int_str(dept7.jrc_total - dept7.jrc_matched)} | {int_str(dept7.jrc_total)} | {pct(dept7.jrc_match_share)} | {int_str(dept7.gaspar_matched)} | {int_str(dept7.gaspar_total - dept7.gaspar_matched)} | {int_str(dept7.gaspar_total)} | {pct(dept7.gaspar_match_share)} |
        | 30 days | {int_str(dept30.jrc_matched)} | {int_str(dept30.jrc_total - dept30.jrc_matched)} | {int_str(dept30.jrc_total)} | {pct(dept30.jrc_match_share)} | {int_str(dept30.gaspar_matched)} | {int_str(dept30.gaspar_total - dept30.gaspar_matched)} | {int_str(dept30.gaspar_total)} | {pct(dept30.gaspar_match_share)} |

        ### National commune-row coverage

        | Window | JRC matched rows | JRC total rows | JRC row match rate | Gaspar matched rows | Gaspar total rows | Gaspar row match rate |
        | --- | ---: | ---: | ---: | ---: | ---: | ---: |
        | 7 days | {int_str(row7.jrc_matched)} | {int_str(row7.jrc_total)} | {pct(row7.jrc_match_share)} | {int_str(row7.gaspar_matched)} | {int_str(row7.gaspar_total)} | {pct(row7.gaspar_match_share)} |
        | 30 days | {int_str(row30.jrc_matched)} | {int_str(row30.jrc_total)} | {pct(row30.jrc_match_share)} | {int_str(row30.gaspar_matched)} | {int_str(row30.gaspar_total)} | {pct(row30.gaspar_match_share)} |

        ### Reading

        - The low commune-level event match is confirmed by the project outputs. Under the strict `7-day` rule, only `{pct(event7.jrc_match_share)}` of JRC events and `{pct(event7.gaspar_match_share)}` of Gaspar event groups find a commune-level partner.
        - Even with the more permissive `30-day` rule, the commune-level event match remains low: `{pct(event30.jrc_match_share)}` for JRC and `{pct(event30.gaspar_match_share)}` for Gaspar.
        - Department-level matching is materially higher, which means a large share of the disagreement comes from commune-level fragmentation rather than from a total absence of overlap.
        - Gaspar contains `{int_str(summary30['gaspar_unique_decrees'])}` decree IDs but `{int_str(summary30['gaspar_unique_event_uids'])}` event groups in the comparison logic, which already tells us that one administrative decree can expand into many date-specific groups.
        """
    ).strip()


def build_statistics_markdown_fr(summary7: dict[str, float], summary30: dict[str, float], coverage7: pd.DataFrame, coverage30: pd.DataFrame) -> str:
    event7 = coverage7[(coverage7["level"] == "commune") & (coverage7["measurement"] == "unique_events")].iloc[0]
    event30 = coverage30[(coverage30["level"] == "commune") & (coverage30["measurement"] == "unique_events")].iloc[0]
    dept7 = coverage7[(coverage7["level"] == "department") & (coverage7["measurement"] == "unique_events")].iloc[0]
    dept30 = coverage30[(coverage30["level"] == "department") & (coverage30["measurement"] == "unique_events")].iloc[0]
    row7 = coverage7[(coverage7["level"] == "commune") & (coverage7["measurement"] == "canonical_rows")].iloc[0]
    row30 = coverage30[(coverage30["level"] == "commune") & (coverage30["measurement"] == "canonical_rows")].iloc[0]

    return dedent(
        f"""
        ## 1. Statistiques d'ensemble

        Les resultats d'ensemble existent deja dans les dossiers de sortie du projet :

        - `data/processed/jrc_gaspar_comparison_flexible_7d`
        - `data/processed/jrc_gaspar_comparison_flexible_30d`

        Le grain evenementiel vient du code de comparaison dans [src/compare_france_jrc_gaspar_flexible.py](/D:/M2_MoSEF/DataCollection/src/compare_france_jrc_gaspar_flexible.py) :

        - `Evenement JRC` = un `jrc_event_id`
        - `Evenement Gaspar` = un `gaspar_event_uid = cod_nat_catnat + dat_deb + dat_fin`

        Remarque importante : cela signifie que le compte "event" pour Gaspar est un proxy de periode de reconnaissance, et non une reconstruction parfaite des episodes physiques d'inondation.

        ### Couverture nationale au niveau evenementiel, regle de match communale

        | Fenetre | JRC matches | JRC exclusifs | JRC total | Taux de match JRC | Gaspar matches | Gaspar exclusifs | Gaspar total | Taux de match Gaspar |
        | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
        | 7 jours | {int_str(event7.jrc_matched)} | {int_str(event7.jrc_total - event7.jrc_matched)} | {int_str(event7.jrc_total)} | {pct(event7.jrc_match_share)} | {int_str(event7.gaspar_matched)} | {int_str(event7.gaspar_total - event7.gaspar_matched)} | {int_str(event7.gaspar_total)} | {pct(event7.gaspar_match_share)} |
        | 30 jours | {int_str(event30.jrc_matched)} | {int_str(event30.jrc_total - event30.jrc_matched)} | {int_str(event30.jrc_total)} | {pct(event30.jrc_match_share)} | {int_str(event30.gaspar_matched)} | {int_str(event30.gaspar_total - event30.gaspar_matched)} | {int_str(event30.gaspar_total)} | {pct(event30.gaspar_match_share)} |

        ### Couverture nationale au niveau evenementiel, regle de match departementale

        | Fenetre | JRC matches | JRC exclusifs | JRC total | Taux de match JRC | Gaspar matches | Gaspar exclusifs | Gaspar total | Taux de match Gaspar |
        | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
        | 7 jours | {int_str(dept7.jrc_matched)} | {int_str(dept7.jrc_total - dept7.jrc_matched)} | {int_str(dept7.jrc_total)} | {pct(dept7.jrc_match_share)} | {int_str(dept7.gaspar_matched)} | {int_str(dept7.gaspar_total - dept7.gaspar_matched)} | {int_str(dept7.gaspar_total)} | {pct(dept7.gaspar_match_share)} |
        | 30 jours | {int_str(dept30.jrc_matched)} | {int_str(dept30.jrc_total - dept30.jrc_matched)} | {int_str(dept30.jrc_total)} | {pct(dept30.jrc_match_share)} | {int_str(dept30.gaspar_matched)} | {int_str(dept30.gaspar_total - dept30.gaspar_matched)} | {int_str(dept30.gaspar_total)} | {pct(dept30.gaspar_match_share)} |

        ### Couverture nationale au niveau des lignes communales

        | Fenetre | Lignes JRC matchees | Lignes JRC totales | Taux de match ligne JRC | Lignes Gaspar matchees | Lignes Gaspar totales | Taux de match ligne Gaspar |
        | --- | ---: | ---: | ---: | ---: | ---: | ---: |
        | 7 jours | {int_str(row7.jrc_matched)} | {int_str(row7.jrc_total)} | {pct(row7.jrc_match_share)} | {int_str(row7.gaspar_matched)} | {int_str(row7.gaspar_total)} | {pct(row7.gaspar_match_share)} |
        | 30 jours | {int_str(row30.jrc_matched)} | {int_str(row30.jrc_total)} | {pct(row30.jrc_match_share)} | {int_str(row30.gaspar_matched)} | {int_str(row30.gaspar_total)} | {pct(row30.gaspar_match_share)} |

        ### Lecture

        - Le faible taux de match communal est confirme par les sorties du projet. Avec la regle stricte `7 jours`, seulement `{pct(event7.jrc_match_share)}` des evenements JRC et `{pct(event7.gaspar_match_share)}` des groupes d'evenements Gaspar trouvent un partenaire au niveau communal.
        - Meme avec la fenetre plus permissive `30 jours`, le taux de match au niveau communal reste faible : `{pct(event30.jrc_match_share)}` pour JRC et `{pct(event30.gaspar_match_share)}` pour Gaspar.
        - Le match departemental est nettement plus eleve, ce qui montre qu'une grande partie du desacord vient de la fragmentation a l'echelle communale plutot que d'une absence totale de recouvrement.
        - Gaspar contient `{int_str(summary30['gaspar_unique_decrees'])}` identifiants de decret mais `{int_str(summary30['gaspar_unique_event_uids'])}` groupes d'evenements dans la logique de comparaison ; cela montre deja qu'un meme decret administratif peut se decomposer en plusieurs groupes dates.
        """
    ).strip()


def build_manual_section_en(example_results: list[dict[str, object]]) -> str:
    lines = [
        "## 2. Manual Visual Checks",
        "",
        "These checks use the commune-activity logic from [src/france_commune_activity.py](/D:/M2_MoSEF/DataCollection/src/france_commune_activity.py) and the France map workflow from [src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py).",
        "",
        "Important distinction:",
        "",
        "- the national statistics above are event-pair statistics from the flexible comparison script",
        "- the manual maps below are period-overlap commune activity maps",
        "",
        "So the two sections are related, but they do not measure exactly the same object.",
        "",
    ]
    for item in example_results:
        lines.extend(
            [
                f"### {item['title_en']}",
                "",
                f"- Quarter: `{item['period_label']}`",
                f"- Region code: `{item['region_code']}` ({item['region_name']})",
                f"- Active communes: `{item['active_communes']}`",
                f"- Both: `{item['both']}`",
                f"- Gaspar only: `{item['gaspar_only']}`",
                f"- JRC only: `{item['jrc_only']}`",
                f"- Top `gaspar_only` departments in this example: {item['gaspar_only_departments']}",
                f"- Top `jrc_only` departments in this example: {item['jrc_only_departments']}",
                "",
                item["rationale_en"],
                "",
                f"![{item['title_en']} comparison map](assets/gaspar_jrc_match_audit/{item['image_name']})",
                "",
                "Interpretation:",
                "",
                item["interpretation_en"],
                "",
                "Public evidence used to contextualize this case:",
                "",
            ]
        )
        for label, url in item["evidence_links"]:
            lines.append(f"- [{label}]({url})")
        lines.append("")
    lines.extend(
        [
            "## 3. Why the Match Rate Is Low",
            "",
            "- `Gaspar` and `JRC` do not start from the same event concept. Gaspar is an administrative recognition system, while JRC is a flood-footprint system derived from satellite-based products.",
            "- A single physical episode can be fragmented differently in the two sources across communes and across dates.",
            "- Commune-level matching is especially hard because one side may recognize runoff, mudflow, or localized urban flooding while the other side captures a wider floodplain footprint.",
            "- The department-level rates show that overlap exists, but the overlap becomes much weaker once the comparison is forced down to the commune-event grain.",
            "- The Gaspar commune harmonization logic matters, but it is not the main explanation here. The unresolved Gaspar share in the map app is small relative to the scale of the national mismatch.",
            "",
            "## 4. Main Conclusion",
            "",
            "The low national match rate is real in the project outputs, and the manual checks suggest that it is not just a cleaning bug. The disagreement mainly reflects differences in event grain, timing fragmentation, and spatial support between an administrative recognition database and a satellite-oriented flood extent product.",
        ]
    )
    return "\n".join(lines)


def build_manual_section_fr(example_results: list[dict[str, object]]) -> str:
    lines = [
        "## 2. Verifications manuelles",
        "",
        "Ces verifications utilisent la logique d'activite communale de [src/france_commune_activity.py](/D:/M2_MoSEF/DataCollection/src/france_commune_activity.py) et le workflow cartographique de [src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py).",
        "",
        "Distinction importante :",
        "",
        "- les statistiques nationales ci-dessus sont des statistiques de paires d'evenements issues du script de comparaison flexible",
        "- les cartes manuelles ci-dessous sont des cartes d'activite communale par recouvrement de periode",
        "",
        "Les deux sections sont donc liees, mais elles ne mesurent pas exactement le meme objet.",
        "",
    ]
    for item in example_results:
        lines.extend(
            [
                f"### {item['title_fr']}",
                "",
                f"- Trimestre: `{item['period_label']}`",
                f"- Code region: `{item['region_code']}` ({item['region_name']})",
                f"- Communes actives: `{item['active_communes']}`",
                f"- Les deux: `{item['both']}`",
                f"- Gaspar seulement: `{item['gaspar_only']}`",
                f"- JRC seulement: `{item['jrc_only']}`",
                f"- Principaux departements `gaspar_only` dans cet exemple: {item['gaspar_only_departments']}",
                f"- Principaux departements `jrc_only` dans cet exemple: {item['jrc_only_departments']}",
                "",
                item["rationale_fr"],
                "",
                f"![{item['title_fr']} carte de comparaison](assets/gaspar_jrc_match_audit/{item['image_name']})",
                "",
                "Interpretation :",
                "",
                item["interpretation_fr"],
                "",
                "Sources publiques utilisees pour contextualiser ce cas :",
                "",
            ]
        )
        for label, url in item["evidence_links"]:
            lines.append(f"- [{label}]({url})")
        lines.append("")
    lines.extend(
        [
            "## 3. Pourquoi le taux de match est faible",
            "",
            "- `Gaspar` et `JRC` ne partent pas du meme concept d'evenement. Gaspar est un systeme de reconnaissance administrative, alors que JRC est un systeme de footprint d'inondation derive de produits satellitaires.",
            "- Un meme episode physique peut etre fragmente differemment dans les deux sources selon les communes et selon les dates.",
            "- Le match communal est particulierement difficile, car une source peut reconnaitre du ruissellement, des coulees de boue ou des inondations urbaines localisees alors que l'autre capte une emprise plus large de plaine inondable.",
            "- Les taux departementaux montrent qu'il existe bien un recouvrement, mais ce recouvrement devient beaucoup plus faible des que la comparaison est forcee au grain commune-evenement.",
            "- La logique d'harmonisation communale de Gaspar compte, mais ce n'est pas l'explication principale ici. La part de lignes Gaspar non resolues dans l'application reste faible par rapport a l'ampleur du mismatch national.",
            "",
            "## 4. Conclusion principale",
            "",
            "Le faible taux de match national est bien reel dans les sorties du projet, et les verifications manuelles suggerent qu'il ne s'agit pas seulement d'un bug de nettoyage. Le desacord reflete surtout des differences de grain evenementiel, de fragmentation temporelle et de support spatial entre une base de reconnaissance administrative et un produit satellitaire d'emprise d'inondation.",
        ]
    )
    return "\n".join(lines)


def render_reports() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    summary7 = read_metric_summary(SUMMARY_7D_DIR)
    summary30 = read_metric_summary(SUMMARY_30D_DIR)
    coverage7 = read_coverage(SUMMARY_7D_DIR)
    coverage30 = read_coverage(SUMMARY_30D_DIR)
    gaspar_rows, jrc_rows, communes = load_activity_sources()
    examples = build_manual_examples()

    example_results: list[dict[str, object]] = []
    for example in examples:
        region_gdf, counts, dept_breakdown = build_example_activity(
            gaspar_rows=gaspar_rows,
            jrc_rows=jrc_rows,
            communes=communes,
            region_code=example.region_code,
            year=example.year,
            quarter=example.quarter,
        )
        _, _, period_label = quarter_period(example.year, example.quarter)
        image_name = f"{example.slug}.png"
        save_example_map(
            region_gdf=region_gdf,
            counts=counts,
            title=example.title_en,
            out_path=ASSET_DIR / image_name,
        )
        gaspar_top = top_departments_text(dept_breakdown, "gaspar_only")
        jrc_top = top_departments_text(dept_breakdown, "jrc_only")
        if example.slug == "grand_est_2021_q3":
            interpretation_en = (
                f"The mismatch is not random. `jrc_only` communes cluster mainly in departments {jrc_top}, "
                f"while `gaspar_only` communes are strongest in {gaspar_top}. The overlap zone exists, but it is much smaller "
                f"than the two source-specific clusters, which suggests that both sources are seeing the same broad northeast flood episode "
                f"with different commune footprints."
            )
            interpretation_fr = (
                f"Le mismatch n'est pas aleatoire. Les communes `jrc_only` se concentrent surtout dans les departements {jrc_top}, "
                f"alors que les communes `gaspar_only` sont plus fortes dans {gaspar_top}. Une zone de recouvrement existe, mais elle reste "
                f"beaucoup plus petite que les deux amas specifiques a chaque source, ce qui suggere que les deux bases voient bien le meme "
                f"grand episode d'inondation du nord-est avec des footprints communaux differents."
            )
        elif example.slug == "bourgogne_franche_comte_2021_q3":
            interpretation_en = (
                f"This case is strongly JRC-dominant. `jrc_only` communes are concentrated in {jrc_top}, whereas `gaspar_only` is concentrated "
                f"almost entirely in {gaspar_top}. Visually, JRC spreads over a wider corridor than Gaspar, which is consistent with a floodplain or "
                f"hydrologic footprint extending beyond the set of communes that entered administrative recognition."
            )
            interpretation_fr = (
                f"Ce cas est fortement domine par JRC. Les communes `jrc_only` se concentrent dans {jrc_top}, alors que le `gaspar_only` est "
                f"presque entierement concentre dans {gaspar_top}. Visuellement, JRC s'etale sur un couloir plus large que Gaspar, ce qui est "
                f"coherent avec une emprise hydrologique ou de plaine inondable plus large que l'ensemble des communes entrees en reconnaissance administrative."
            )
        else:
            interpretation_en = (
                f"This case is strongly Gaspar-dominant. `gaspar_only` communes are concentrated in {gaspar_top}, while the small `jrc_only` remainder "
                f"is limited to {jrc_top}. The visual reading is that a very large administratively recognized event exists, but JRC only overlaps a narrower "
                f"subset of the affected communes."
            )
            interpretation_fr = (
                f"Ce cas est fortement domine par Gaspar. Les communes `gaspar_only` se concentrent dans {gaspar_top}, alors que le petit reliquat `jrc_only` "
                f"reste limite a {jrc_top}. La lecture visuelle est donc celle d'un evenement tres largement reconnu administrativement, alors que JRC ne recouvre "
                f"qu'un sous-ensemble plus etroit des communes touchees."
            )
        example_results.append(
            {
                "title_en": example.title_en,
                "title_fr": example.title_fr,
                "region_code": example.region_code,
                "region_name": REGION_NAMES.get(example.region_code, example.region_code),
                "period_label": period_label,
                "image_name": image_name,
                "rationale_en": example.rationale_en,
                "rationale_fr": example.rationale_fr,
                "interpretation_en": interpretation_en,
                "interpretation_fr": interpretation_fr,
                "evidence_links": example.evidence_links,
                "active_communes": f"{counts['active_communes']:,}",
                "both": f"{counts['both']:,}",
                "gaspar_only": f"{counts['gaspar_only']:,}",
                "jrc_only": f"{counts['jrc_only']:,}",
                "gaspar_only_departments": gaspar_top,
                "jrc_only_departments": jrc_top,
            }
        )

    en_content = "\n\n".join(
        [
            "# Gaspar vs JRC in France: Match Statistics and Manual Visual Checks",
            "",
            "This note documents two things:",
            "",
            "1. national match statistics from the existing France comparison outputs",
            "2. manual quarter-region visual checks based on the France commune activity map logic",
            "",
            "This report can be regenerated with [src/build_gaspar_jrc_match_audit_docs.py](/D:/M2_MoSEF/DataCollection/src/build_gaspar_jrc_match_audit_docs.py).",
            "",
            "Project inputs and logic used here:",
            "",
            "- [src/compare_france_jrc_gaspar_flexible.py](/D:/M2_MoSEF/DataCollection/src/compare_france_jrc_gaspar_flexible.py)",
            "- [src/france_commune_activity.py](/D:/M2_MoSEF/DataCollection/src/france_commune_activity.py)",
            "- [src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py)",
            "- `data/processed/jrc_gaspar_comparison_flexible_7d`",
            "- `data/processed/jrc_gaspar_comparison_flexible_30d`",
            "",
            build_statistics_markdown_en(summary7, summary30, coverage7, coverage30),
            build_manual_section_en(example_results),
        ]
    )

    fr_content = "\n\n".join(
        [
            "# Gaspar vs JRC en France : statistiques de match et verifications visuelles manuelles",
            "",
            "Cette note documente deux choses :",
            "",
            "1. les statistiques nationales de match a partir des sorties de comparaison deja presentes dans le projet",
            "2. des verifications visuelles manuelles par trimestre et par region a partir de la logique de carte d'activite communale",
            "",
            "Ce rapport peut etre regenere avec [src/build_gaspar_jrc_match_audit_docs.py](/D:/M2_MoSEF/DataCollection/src/build_gaspar_jrc_match_audit_docs.py).",
            "",
            "Inputs et logique du projet utilises ici :",
            "",
            "- [src/compare_france_jrc_gaspar_flexible.py](/D:/M2_MoSEF/DataCollection/src/compare_france_jrc_gaspar_flexible.py)",
            "- [src/france_commune_activity.py](/D:/M2_MoSEF/DataCollection/src/france_commune_activity.py)",
            "- [src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py)",
            "- `data/processed/jrc_gaspar_comparison_flexible_7d`",
            "- `data/processed/jrc_gaspar_comparison_flexible_30d`",
            "",
            build_statistics_markdown_fr(summary7, summary30, coverage7, coverage30),
            build_manual_section_fr(example_results),
        ]
    )

    en_content = re.sub(r"\n{3,}", "\n\n", en_content).strip() + "\n"
    fr_content = re.sub(r"\n{3,}", "\n\n", fr_content).strip() + "\n"

    (DOCS_DIR / "gaspar_jrc_match_audit_en.md").write_text(en_content, encoding="utf-8")
    (DOCS_DIR / "gaspar_jrc_match_audit_fr.md").write_text(fr_content, encoding="utf-8")


def main() -> None:
    render_reports()
    print(f"Wrote {DOCS_DIR / 'gaspar_jrc_match_audit_en.md'}")
    print(f"Wrote {DOCS_DIR / 'gaspar_jrc_match_audit_fr.md'}")
    print(f"Wrote assets under {ASSET_DIR}")


if __name__ == "__main__":
    main()
