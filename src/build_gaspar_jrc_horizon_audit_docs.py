from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
import pandas as pd

from build_gaspar_jrc_match_audit_docs import (
    DOCS_DIR,
    REGION_NAMES,
    build_example_activity,
    build_statistics_markdown_en,
    build_statistics_markdown_fr,
    int_str,
    load_activity_sources,
    pct,
    quarter_period,
    read_coverage,
    read_metric_summary,
    save_example_map,
    top_departments_text,
    SUMMARY_7D_DIR,
    SUMMARY_30D_DIR,
)


ASSET_DIR = DOCS_DIR / "assets" / "gaspar_jrc_horizon_audit"
RANKING_CSV = ASSET_DIR / "region_quarter_mismatch_2015_2024.csv"
EN_DOC = DOCS_DIR / "gaspar_jrc_horizon_audit_en.md"
FR_DOC = DOCS_DIR / "gaspar_jrc_horizon_audit_fr.md"


@dataclass(frozen=True)
class HorizonCase:
    slug: str
    title_en: str
    title_fr: str
    region_code: str
    year: int
    quarter: int
    selection_reason_en: str
    selection_reason_fr: str
    evidence_links: list[tuple[str, str]]


@dataclass(frozen=True)
class NotablePeriod:
    title_en: str
    title_fr: str
    region_code: str
    year: int
    quarter: int
    profile_en: str
    profile_fr: str
    why_it_matters_en: str
    why_it_matters_fr: str
    evidence_links: list[tuple[str, str]]


def abs_doc_link(path: Path) -> str:
    return f"/{path.resolve().as_posix()}"


def build_quarter_grid(start_year: int = 2015, end_year: int = 2024) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in range(start_year, end_year + 1):
        for quarter, month in [(1, 1), (2, 4), (3, 7), (4, 10)]:
            start = pd.Timestamp(year=year, month=month, day=1)
            end = start + pd.offsets.QuarterEnd(startingMonth=month + 2)
            rows.append(
                {
                    "year": year,
                    "quarter": quarter,
                    "period_label": f"{year}-Q{quarter}",
                    "quarter_start": start.normalize(),
                    "quarter_end": end.normalize(),
                }
            )
    return pd.DataFrame(rows)


def expand_rows_to_quarters(
    rows: pd.DataFrame,
    *,
    commune_regions: pd.DataFrame,
    quarter_grid: pd.DataFrame,
) -> pd.DataFrame:
    use = rows[["insee_com", "activity_start_date", "activity_end_date"]].dropna().copy()
    use["activity_start_date"] = pd.to_datetime(use["activity_start_date"])
    use["activity_end_date"] = pd.to_datetime(use["activity_end_date"])
    use = use.merge(commune_regions, on="insee_com", how="left")
    use = use.dropna(subset=["region_code"])
    use["join_key"] = 1

    quarter_join = quarter_grid.copy()
    quarter_join["join_key"] = 1

    expanded = use.merge(quarter_join, on="join_key", how="inner")
    expanded = expanded[
        expanded["quarter_start"].le(expanded["activity_end_date"])
        & expanded["quarter_end"].ge(expanded["activity_start_date"])
    ].copy()

    return expanded[["region_code", "year", "quarter", "period_label", "insee_com"]].drop_duplicates()


def compute_region_quarter_ranking(
    *,
    gaspar_rows: pd.DataFrame,
    jrc_rows: pd.DataFrame,
    communes: pd.DataFrame,
) -> pd.DataFrame:
    quarter_grid = build_quarter_grid()
    commune_regions = (
        communes[["insee_com", "insee_reg"]]
        .dropna(subset=["insee_com"])
        .drop_duplicates(subset=["insee_com"])
        .rename(columns={"insee_reg": "region_code"})
    )
    commune_regions["region_code"] = commune_regions["region_code"].astype(str)

    gaspar_quarters = expand_rows_to_quarters(
        gaspar_rows,
        commune_regions=commune_regions,
        quarter_grid=quarter_grid,
    )
    jrc_quarters = expand_rows_to_quarters(
        jrc_rows,
        commune_regions=commune_regions,
        quarter_grid=quarter_grid,
    )

    gaspar_sets = (
        gaspar_quarters.groupby(["region_code", "year", "quarter", "period_label"])["insee_com"]
        .agg(set)
        .rename("gaspar_set")
        .reset_index()
    )
    jrc_sets = (
        jrc_quarters.groupby(["region_code", "year", "quarter", "period_label"])["insee_com"]
        .agg(set)
        .rename("jrc_set")
        .reset_index()
    )

    keys = pd.concat(
        [
            gaspar_sets[["region_code", "year", "quarter", "period_label"]],
            jrc_sets[["region_code", "year", "quarter", "period_label"]],
        ],
        ignore_index=True,
    ).drop_duplicates()

    ranking = (
        keys.merge(gaspar_sets, on=["region_code", "year", "quarter", "period_label"], how="left")
        .merge(jrc_sets, on=["region_code", "year", "quarter", "period_label"], how="left")
        .copy()
    )
    ranking["gaspar_set"] = ranking["gaspar_set"].apply(lambda value: value if isinstance(value, set) else set())
    ranking["jrc_set"] = ranking["jrc_set"].apply(lambda value: value if isinstance(value, set) else set())

    ranking["both"] = ranking.apply(lambda row: len(row.gaspar_set & row.jrc_set), axis=1)
    ranking["gaspar_only"] = ranking.apply(lambda row: len(row.gaspar_set - row.jrc_set), axis=1)
    ranking["jrc_only"] = ranking.apply(lambda row: len(row.jrc_set - row.gaspar_set), axis=1)
    ranking["active_communes"] = ranking["both"] + ranking["gaspar_only"] + ranking["jrc_only"]
    ranking["mismatch_communes"] = ranking["gaspar_only"] + ranking["jrc_only"]
    ranking["overlap_share"] = np.where(
        ranking["active_communes"].gt(0),
        ranking["both"] / ranking["active_communes"],
        np.nan,
    )
    ranking["gaspar_share"] = np.where(
        ranking["active_communes"].gt(0),
        ranking["gaspar_only"] / ranking["active_communes"],
        np.nan,
    )
    ranking["jrc_share"] = np.where(
        ranking["active_communes"].gt(0),
        ranking["jrc_only"] / ranking["active_communes"],
        np.nan,
    )
    ranking["region_name"] = ranking["region_code"].map(REGION_NAMES).fillna(ranking["region_code"])
    ranking["dominant_source"] = np.select(
        [
            ranking["jrc_only"].gt(ranking["gaspar_only"]),
            ranking["gaspar_only"].gt(ranking["jrc_only"]),
        ],
        ["JRC", "Gaspar"],
        default="Balanced",
    )
    ranking = ranking[ranking["active_communes"].gt(0)].copy()

    return ranking.sort_values(
        ["mismatch_communes", "active_communes", "region_code", "year", "quarter"],
        ascending=[False, False, True, True, True],
        kind="stable",
    ).reset_index(drop=True)


def markdown_table(df: pd.DataFrame) -> str:
    lines = [
        "| " + " | ".join(df.columns) + " |",
        "| " + " | ".join(["---"] * len(df.columns)) + " |",
    ]
    for _, row in df.iterrows():
        values = [str(row[column]) for column in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def format_ranking_table(df: pd.DataFrame, *, rows: int) -> pd.DataFrame:
    subset = df.head(rows).copy()
    return pd.DataFrame(
        {
            "Period": subset["period_label"],
            "Region": subset["region_name"],
            "Active communes": subset["active_communes"].map(int_str),
            "Both": subset["both"].map(int_str),
            "Gaspar only": subset["gaspar_only"].map(int_str),
            "JRC only": subset["jrc_only"].map(int_str),
            "Mismatch communes": subset["mismatch_communes"].map(int_str),
            "Overlap share": subset["overlap_share"].map(pct),
        }
    )


def format_ranking_table_fr(df: pd.DataFrame, *, rows: int) -> pd.DataFrame:
    subset = df.head(rows).copy()
    return pd.DataFrame(
        {
            "Periode": subset["period_label"],
            "Region": subset["region_name"],
            "Communes actives": subset["active_communes"].map(int_str),
            "Les deux": subset["both"].map(int_str),
            "Gaspar seulement": subset["gaspar_only"].map(int_str),
            "JRC seulement": subset["jrc_only"].map(int_str),
            "Communes en desacord": subset["mismatch_communes"].map(int_str),
            "Part de recouvrement": subset["overlap_share"].map(pct),
        }
    )


def build_horizon_cases() -> list[HorizonCase]:
    return [
        HorizonCase(
            slug="centre_val_de_loire_2016_q2",
            title_en="Centre-Val de Loire, Q2 2016",
            title_fr="Centre-Val de Loire, T2 2016",
            region_code="24",
            year=2016,
            quarter=2,
            selection_reason_en=(
                "Chosen as the strongest high-activity Gaspar-dominant quarter in the 2015-2024 horizon."
            ),
            selection_reason_fr=(
                "Choisi comme le trimestre a forte activite le plus domine par Gaspar sur l'horizon 2015-2024."
            ),
            evidence_links=[
                ("Centre-Val de Loire prefecture, regional floods page", "https://www.prefectures-regions.gouv.fr/centre-val-de-loire/Actualites/Principales/Inondations-en-region-Centre-Val-de-Loire"),
                ("DREAL Centre-Val de Loire, return on late May / early June 2016 floods", "https://www.centre-val-de-loire.developpement-durable.gouv.fr/retour-sur-les-crues-de-fin-mai-et-debut-juin-2016-a3155.html"),
                ("Ministry of the Interior, return-experience report on May-June 2016 floods", "https://www.interieur.gouv.fr/fr/Publications/Rapports-de-l-IGA/Securite-civile/Inondations-de-mai-et-de-juin-2016-dans-les-bassins-moyens-de-la-Seine-et-de-la-Loire-retour-d-experience"),
                ("Loiret department, remembrance page for May-June 2016 floods", "https://www.loiret.fr/actualite/inondations-de-mai-juin-2016-le-loiret-se-souvient"),
            ],
        ),
        HorizonCase(
            slug="grand_est_2018_q1",
            title_en="Grand Est, Q1 2018",
            title_fr="Grand Est, T1 2018",
            region_code="44",
            year=2018,
            quarter=1,
            selection_reason_en=(
                "Chosen because it is the single largest region-quarter mismatch in the 2015-2024 ranking."
            ),
            selection_reason_fr=(
                "Choisi car il s'agit du plus grand mismatch region-trimestre de tout le classement 2015-2024."
            ),
            evidence_links=[
                ("Meteo-France, January 2018 remarkable floods", "https://meteofrance.com/magazine/meteo-histoire/les-grands-evenements/janvier-2018-inondations-et-crues-remarquables"),
                ("Bas-Rhin prefecture, 2018 press archive with 23 January flood bulletin", "https://www.bas-rhin.gouv.fr/Actualites/Communiques-Agenda/Archive-CP/Communiques-2018"),
                ("Reperes de crues, Moselle January 2018 flood mark near Metz", "https://www.reperesdecrues.developpement-durable.gouv.fr/repere/metz-culee-amont-rive-gauche-du-pont-d153z-2eme-pont-en-aval-de-la-confluence-avec-la-seille"),
                ("Rhin-Meuse flood-risk plan, generalized January 2018 flood on Meuse and Rhine basins", "https://www.grand-est.developpement-durable.gouv.fr/IMG/pdf/pgri-rhin-meuse_approuve.pdf"),
            ],
        ),
        HorizonCase(
            slug="bourgogne_franche_comte_2018_q1",
            title_en="Bourgogne-Franche-Comte, Q1 2018",
            title_fr="Bourgogne-Franche-Comte, T1 2018",
            region_code="27",
            year=2018,
            quarter=1,
            selection_reason_en=(
                "Chosen as the second-largest mismatch quarter and as the neighboring winter-flood corridor to the Grand Est 2018 case."
            ),
            selection_reason_fr=(
                "Choisi comme deuxieme plus grand trimestre en mismatch et comme couloir voisin des crues hivernales du cas Grand Est 2018."
            ),
            evidence_links=[
                ("Bourgogne-Franche-Comte hydrological bulletin, special January 2018 flood issue", "https://www.bourgogne-franche-comte.developpement-durable.gouv.fr/IMG/pdf/bull_bfc_01_2018_cle11613d.pdf"),
                ("Doubs prefecture, orange flood vigilance, 23 January 2018", "https://www.doubs.gouv.fr/layout/set/print/Publications/Salle-de-Presse/Communiques-de-presse/Annee-2018/Le-Doubs-place-en-vigilance-orange-inondations"),
                ("Saone-et-Loire prefecture, orange flood vigilance point, 25 January 2018", "https://www.saone-et-loire.gouv.fr/Actualites/Salle-de-presse/L-historique-des-annees-precedentes/2018/Janvier/Alerte-crues-vigilance-orange-en-Saone-et-Loire-point-de-situation"),
                ("Ministry of the Interior, late January 2018 floods and CatNat recognition", "https://www.interieur.gouv.fr/archive/inondations-de-fin-janvier-2018-275-communes-reconnues-en-etat-de-catastrophe-naturelle"),
            ],
        ),
        HorizonCase(
            slug="grand_est_2021_q3",
            title_en="Grand Est, Q3 2021",
            title_fr="Grand Est, T3 2021",
            region_code="44",
            year=2021,
            quarter=3,
            selection_reason_en=(
                "Chosen as a mixed July 2021 case where both Gaspar-only and JRC-only clusters are supported by public evidence."
            ),
            selection_reason_fr=(
                "Choisi comme cas mixte de juillet 2021, ou les clusters Gaspar-only et JRC-only sont tous deux soutenus par des sources publiques."
            ),
            evidence_links=[
                ("L'Est Republicain, Bar-le-Duc under water, 15 July 2021", "https://www.estrepublicain.fr/faits-divers-justice/2021/07/15/inondations-spectaculaires-a-bar-le-duc-la-ville-toute-une-journee-les-pieds-dans-l-eau"),
                ("Meuse prefecture, July 13-15 2021 flood procedure", "https://www.meuse.gouv.fr/Politiques-publiques/Securite/Demande-de-catastrophes-naturelles-Inondations-du-13-au-15-juillet-2021"),
                ("Champagne FM, Asfeld pumping operations, 14 July 2021", "https://www.champagnefm.com/news/a-deborde-56670"),
                ("Radio 8 Ardennes, flood situation update, 16 July 2021", "https://radio8fm.com/infos/article/16614-Pluie_inondations_Point_de_situation_dans_les_Ardennes_ce_16_juillet_2021_a_19h00"),
                ("Reperes de crues, Vieux-les-Asfeld", "https://www.reperesdecrues.developpement-durable.gouv.fr/site/sortie-du-village-en-direction-de-avaux"),
            ],
        ),
        HorizonCase(
            slug="grand_est_2024_q2",
            title_en="Grand Est, Q2 2024",
            title_fr="Grand Est, T2 2024",
            region_code="44",
            year=2024,
            quarter=2,
            selection_reason_en=(
                "Chosen as a recent end-of-horizon case with very large mismatch and clear public evidence from the May 17-20, 2024 flood episode."
            ),
            selection_reason_fr=(
                "Choisi comme cas recent en fin d'horizon, avec un mismatch tres large et des preuves publiques claires autour des inondations du 17 au 20 mai 2024."
            ),
            evidence_links=[
                ("Ecology ministry press release on Grand Est floods, 18 May 2024", "https://www.ecologie.gouv.fr/presse/inondations-grand-est-christophe-bechu-appelle-vigilance-habitants-rappelle-bons"),
                ("Moselle prefecture, accelerated CatNat procedure for May 2024 floods", "https://www.moselle.gouv.fr/Actualites/Securite/Protection-publique-et-securite-civile/Inondations-mai-2024-Procedure-de-reconnaissance-de-l-Etat-de-catastrophe-naturelle-acceleree"),
                ("DREAL Grand Est hydrological bulletin, May 2024", "https://www.grand-est.developpement-durable.gouv.fr/bsh-grand-est-mai-2024-a22699.html"),
                ("Moselle state services, after-action note on the May 2024 floods", "https://www.moselle.gouv.fr/Publications/Actu-Moselle-Le-magazine-de-l-Etat-en-Moselle/Annee-2024/La-lettre-des-services-de-l-Etat-en-Moselle-n-67/La-Moselle-frappee-par-les-inondations"),
            ],
        ),
    ]


def build_notable_periods() -> list[NotablePeriod]:
    return [
        NotablePeriod(
            title_en="Ile-de-France, Q2 2016",
            title_fr="Ile-de-France, T2 2016",
            region_code="11",
            year=2016,
            quarter=2,
            profile_en="Very large Gaspar-dominant quarter linked to the Seine / Loing late-May and early-June 2016 flood family.",
            profile_fr="Tres grand trimestre domine par Gaspar, lie a la famille de crues Seine / Loing de fin mai et debut juin 2016.",
            why_it_matters_en=(
                "This period is not one of the five mapped cases because it belongs to the same national flood family as Centre-Val de Loire 2016, "
                "but it confirms that the 2016 mismatch extends well beyond one region."
            ),
            why_it_matters_fr=(
                "Cette periode ne fait pas partie des cinq cas cartographies car elle appartient a la meme famille nationale de crues que Centre-Val de Loire 2016, "
                "mais elle confirme que le mismatch de 2016 depasse largement une seule region."
            ),
            evidence_links=[
                ("DRIEAT Ile-de-France, one year after the May-June 2016 flood", "https://www.drieat.ile-de-france.developpement-durable.gouv.fr/crue-de-mai-juin-2016-le-point-un-an-apres-r1507.html"),
                ("Ministry of the Interior, return-experience report on May-June 2016 floods", "https://www.interieur.gouv.fr/documentation/rapports/inondations-de-mai-et-juin-2016-dans-bassins-moyens-de-seine-et-de-loire-retour-dexperience-16080-r.html"),
            ],
        ),
        NotablePeriod(
            title_en="Provence-Alpes-Cote d'Azur, Q4 2019",
            title_fr="Provence-Alpes-Cote d'Azur, T4 2019",
            region_code="93",
            year=2019,
            quarter=4,
            profile_en="Strong Gaspar-dominant quarter linked to the November 2019 floods in the Var and Alpes-Maritimes.",
            profile_fr="Trimestre fortement domine par Gaspar, lie aux inondations de novembre 2019 dans le Var et les Alpes-Maritimes.",
            why_it_matters_en=(
                "This case shows that the mismatch is not limited to the northeast or to 2016. Mediterranean flood episodes also create large commune-level disagreement."
            ),
            why_it_matters_fr=(
                "Ce cas montre que le mismatch ne se limite ni au nord-est ni a 2016. Les episodes mediterraneens produisent eux aussi un fort desacord au niveau communal."
            ),
            evidence_links=[
                ("Legifrance, CatNat recognition for the 22-24 November 2019 floods", "https://www.legifrance.gouv.fr/jorf/article_jo/JORFARTI000041717653"),
                ("Official Rhone-Mediterranee flood-event report, Var floods of 22-24 November 2019", "https://www.auvergne-rhone-alpes.developpement-durable.gouv.fr/IMG/pdf/20240606-epri-bassinrm-receuil_evts.pdf"),
            ],
        ),
        NotablePeriod(
            title_en="Hauts-de-France, Q4 2023",
            title_fr="Hauts-de-France, T4 2023",
            region_code="32",
            year=2023,
            quarter=4,
            profile_en="Strong Gaspar-dominant quarter linked to the November 2023 Pas-de-Calais and Nord floods.",
            profile_fr="Trimestre fortement domine par Gaspar, lie aux inondations de novembre 2023 dans le Pas-de-Calais et le Nord.",
            why_it_matters_en=(
                "This recent case confirms that major flood episodes can remain strongly Gaspar-heavy even when public evidence and national response were intense."
            ),
            why_it_matters_fr=(
                "Ce cas recent confirme que de grands episodes de crue peuvent rester fortement orientes vers Gaspar, meme lorsque les preuves publiques et la reponse nationale sont tres visibles."
            ),
            evidence_links=[
                ("Hauts-de-France regional prefecture, flood situation update, 22 November 2023", "https://www.prefectures-regions.gouv.fr/hauts-de-france/Actualites/Crues-dans-le-Pas-de-Calais-et-le-Nord-point-de-situation-sur-les-moyens-mobilises-au-22.11"),
                ("Service-Public, CatNat recognition for 205 communes after the November 2023 floods", "https://www.service-public.gouv.fr/particuliers/actualites/A16928?lang=en"),
                ("info.gouv.fr, national government response to the Hauts-de-France floods", "https://www.info.gouv.fr/actualite/le-gouvernement-se-mobilise-face-aux-inondations"),
            ],
        ),
    ]


def build_period_ranking_section_en(ranking: pd.DataFrame) -> str:
    top_mismatch = format_ranking_table(ranking, rows=12)
    top_gaspar = format_ranking_table(
        ranking[ranking["active_communes"].ge(100)].sort_values(
            ["gaspar_only", "active_communes"],
            ascending=[False, False],
            kind="stable",
        ),
        rows=8,
    )
    top_jrc = format_ranking_table(
        ranking[ranking["active_communes"].ge(100)].sort_values(
            ["jrc_only", "active_communes"],
            ascending=[False, False],
            kind="stable",
        ),
        rows=8,
    )

    return "\n".join(
        [
            "## 2. Periods With The Largest Manual Mismatch Across 2015-2024",
            "",
            "To extend the manual checks beyond the already documented 2021 examples, I ranked every France region-quarter from `2015-Q1` to `2024-Q4` with the same commune-activity logic used by the Streamlit app.",
            "",
            "Important distinction:",
            "",
            "- this ranking is based on **period-overlap commune activity**",
            "- it is not the same as the **event-pair statistics** from the flexible comparison script",
            "",
            "The ranking file used for this section is saved at:",
            "",
            f"- [region_quarter_mismatch_2015_2024.csv]({abs_doc_link(RANKING_CSV)})",
            "",
            "### Top region-quarter combinations by disagreement communes",
            "",
            markdown_table(top_mismatch),
            "",
            "### Strongest Gaspar-dominant periods",
            "",
            markdown_table(top_gaspar),
            "",
            "### Strongest JRC-dominant periods",
            "",
            markdown_table(top_jrc),
            "",
            "### Reading",
            "",
            "- The largest mismatch periods are not concentrated in one single year; they span `2016`, `2018`, `2021`, and `2024`.",
            "- The strongest high-activity Gaspar-dominant period is `Centre-Val de Loire, 2016-Q2`, followed by `Ile-de-France, 2016-Q2`.",
            "- The strongest JRC-dominant periods are concentrated in the winter 2018 flood family (`Grand Est, 2018-Q1` and `Bourgogne-Franche-Comte, 2018-Q1`) and in recent Grand Est / southwest quarters at the end of the source horizon.",
            "- Some end-of-horizon `2024` cases may be more sensitive to administrative timing lag than older quarters. That timing-lag point is an inference from the position of the period in the source horizon and from the CatNat process, not a direct measurement from the comparison tables.",
            "",
        ]
    )


def build_period_ranking_section_fr(ranking: pd.DataFrame) -> str:
    top_mismatch = format_ranking_table_fr(ranking, rows=12)
    top_gaspar = format_ranking_table_fr(
        ranking[ranking["active_communes"].ge(100)].sort_values(
            ["gaspar_only", "active_communes"],
            ascending=[False, False],
            kind="stable",
        ),
        rows=8,
    )
    top_jrc = format_ranking_table_fr(
        ranking[ranking["active_communes"].ge(100)].sort_values(
            ["jrc_only", "active_communes"],
            ascending=[False, False],
            kind="stable",
        ),
        rows=8,
    )

    return "\n".join(
        [
            "## 2. Periodes ou le mismatch manuel est le plus fort sur 2015-2024",
            "",
            "Pour etendre les verifications manuelles au-dela des exemples 2021 deja documentes, j'ai classe chaque region-trimestre francaise de `2015-T1` a `2024-T4` avec la meme logique d'activite communale que celle utilisee dans l'application Streamlit.",
            "",
            "Distinction importante :",
            "",
            "- ce classement repose sur **l'activite communale par recouvrement de periode**",
            "- ce n'est pas la meme chose que les **statistiques de paires d'evenements** du script de comparaison flexible",
            "",
            "Le fichier de classement utilise ici est enregistre ici :",
            "",
            f"- [region_quarter_mismatch_2015_2024.csv]({abs_doc_link(RANKING_CSV)})",
            "",
            "### Principaux couples region-trimestre par nombre de communes en desacord",
            "",
            markdown_table(top_mismatch),
            "",
            "### Periodes les plus dominees par Gaspar",
            "",
            markdown_table(top_gaspar),
            "",
            "### Periodes les plus dominees par JRC",
            "",
            markdown_table(top_jrc),
            "",
            "### Lecture",
            "",
            "- Les plus grands mismatch ne se concentrent pas sur une seule annee ; ils couvrent `2016`, `2018`, `2021` et `2024`.",
            "- Le trimestre a forte activite le plus domine par Gaspar est `Centre-Val de Loire, 2016-T2`, suivi par `Ile-de-France, 2016-T2`.",
            "- Les periodes les plus dominees par JRC se concentrent sur la famille de crues hivernales de 2018 (`Grand Est, 2018-T1` et `Bourgogne-Franche-Comte, 2018-T1`) ainsi que sur des trimestres recents du Grand Est et du sud-ouest en fin d'horizon des sources.",
            "- Certains cas de `2024`, situes en fin d'horizon des donnees, peuvent etre plus sensibles a un decalage temporel administratif que les trimestres plus anciens. Ce point sur le decalage temporel est une inference basee sur la position de la periode dans l'horizon des sources et sur la procedure CatNat, pas une mesure directe issue des tables de comparaison.",
            "",
        ]
    )


def build_notable_periods_section_en(ranking: pd.DataFrame) -> str:
    lines = [
        "## 3. Other Important Flood Periods In The 2015-2024 Horizon",
        "",
        "The five mapped cases are not the whole story. The ranking also highlights other historically important flood periods that help explain why the national commune-level match stays low.",
        "",
    ]
    for period in build_notable_periods():
        row = ranking[
            ranking["region_code"].eq(period.region_code)
            & ranking["year"].eq(period.year)
            & ranking["quarter"].eq(period.quarter)
        ].copy()
        if row.empty:
            continue
        first = row.iloc[0]
        lines.extend(
            [
                f"### {period.title_en}",
                "",
                f"- Quarter: `{first['period_label']}`",
                f"- Profile in the ranking: {period.profile_en}",
                f"- Active communes: `{int_str(first['active_communes'])}`",
                f"- Both: `{int_str(first['both'])}`",
                f"- Gaspar only: `{int_str(first['gaspar_only'])}`",
                f"- JRC only: `{int_str(first['jrc_only'])}`",
                f"- Overlap share: `{pct(first['overlap_share'])}`",
                f"- Why it matters: {period.why_it_matters_en}",
                "",
                "Evidence links:",
                "",
            ]
        )
        for label, url in period.evidence_links:
            lines.append(f"- [{label}]({url})")
        lines.append("")
    return "\n".join(lines)


def build_notable_periods_section_fr(ranking: pd.DataFrame) -> str:
    lines = [
        "## 3. Autres periodes importantes sur l'horizon 2015-2024",
        "",
        "Les cinq cas cartographies ne racontent pas toute l'histoire. Le classement met aussi en evidence d'autres periodes d'inondation historiquement importantes qui aident a comprendre pourquoi le taux de match communal national reste faible.",
        "",
    ]
    for period in build_notable_periods():
        row = ranking[
            ranking["region_code"].eq(period.region_code)
            & ranking["year"].eq(period.year)
            & ranking["quarter"].eq(period.quarter)
        ].copy()
        if row.empty:
            continue
        first = row.iloc[0]
        lines.extend(
            [
                f"### {period.title_fr}",
                "",
                f"- Trimestre: `{first['period_label']}`",
                f"- Profil dans le classement: {period.profile_fr}",
                f"- Communes actives: `{int_str(first['active_communes'])}`",
                f"- Les deux: `{int_str(first['both'])}`",
                f"- Gaspar seulement: `{int_str(first['gaspar_only'])}`",
                f"- JRC seulement: `{int_str(first['jrc_only'])}`",
                f"- Part de recouvrement: `{pct(first['overlap_share'])}`",
                f"- Pourquoi c'est important: {period.why_it_matters_fr}",
                "",
                "Liens de preuve :",
                "",
            ]
        )
        for label, url in period.evidence_links:
            lines.append(f"- [{label}]({url})")
        lines.append("")
    return "\n".join(lines)


def build_case_interpretation(
    case: HorizonCase,
    *,
    gaspar_top: str,
    jrc_top: str,
    counts: dict[str, int],
) -> tuple[str, str]:
    if case.slug == "centre_val_de_loire_2016_q2":
        return (
            (
                f"This is the strongest high-activity Gaspar-dominant period in the horizon. `gaspar_only` communes are concentrated in {gaspar_top}, "
                f"while the small `jrc_only` remainder is limited to {jrc_top}. The external sources clearly confirm a major late-May and early-June 2016 flood, "
                f"so the weak JRC overlap is better read as a footprint and timing difference than as an absence of flooding."
            ),
            (
                f"C'est le trimestre a forte activite le plus domine par Gaspar sur tout l'horizon. Les communes `gaspar_only` se concentrent dans {gaspar_top}, "
                f"alors que le petit reliquat `jrc_only` reste limite a {jrc_top}. Les sources externes confirment clairement un grand episode de crues entre fin mai "
                f"et debut juin 2016 ; le faible recouvrement JRC se lit donc plutot comme une difference d'emprise et de timing que comme une absence d'inondation."
            ),
        )
    if case.slug == "grand_est_2018_q1":
        return (
            (
                f"This is the single largest region-quarter mismatch in the ranking. `jrc_only` communes cluster heavily in {jrc_top}, while `gaspar_only` remains limited to {gaspar_top}. "
                f"Official hydrology and flood-marker sources confirm generalized January 2018 flooding across the northeast, which is consistent with a very broad hydrologic event whose raster footprint is much wider than the administrative overlap."
            ),
            (
                f"Il s'agit du plus grand mismatch region-trimestre de tout le classement. Les communes `jrc_only` se concentrent tres fortement dans {jrc_top}, "
                f"alors que `gaspar_only` reste limite a {gaspar_top}. Les sources hydrologiques officielles et les reperes de crues confirment des inondations generalisees "
                f"en janvier 2018 sur le nord-est, ce qui est coherent avec un evenement hydrologique tres large dont l'emprise raster depasse nettement la zone de recouvrement administrative."
            ),
        )
    if case.slug == "bourgogne_franche_comte_2018_q1":
        return (
            (
                f"This neighboring winter 2018 case is also strongly JRC-dominant. `jrc_only` communes are concentrated in {jrc_top}, whereas `gaspar_only` is much smaller in {gaspar_top}. "
                f"The regional hydrology bulletin and prefecture alerts confirm two January 2018 flood sequences, so the pattern again looks like a very wide flood corridor with limited administrative overlap."
            ),
            (
                f"Ce cas voisin de l'hiver 2018 est lui aussi fortement domine par JRC. Les communes `jrc_only` se concentrent dans {jrc_top}, alors que `gaspar_only` reste beaucoup plus reduit dans {gaspar_top}. "
                f"Le bulletin hydrologique regional et les alertes prefectorales confirment deux sequences de crues en janvier 2018 ; le motif ressemble donc encore a un couloir de crue tres large avec un recouvrement administratif limite."
            ),
        )
    if case.slug == "grand_est_2021_q3":
        return (
            (
                f"This remains a mixed case rather than a single-source extreme. `jrc_only` communes cluster mainly in {jrc_top}, while `gaspar_only` communes are strongest in {gaspar_top}. "
                f"Because public evidence exists on both sides, this example is especially useful for showing that the mismatch is not just noise or unmatched commune codes."
            ),
            (
                f"Ce cas reste un cas mixte plutot qu'un extreme a source unique. Les communes `jrc_only` se concentrent surtout dans {jrc_top}, alors que les communes `gaspar_only` sont plus fortes dans {gaspar_top}. "
                f"Comme il existe des preuves publiques des deux cotes, cet exemple est particulierement utile pour montrer que le mismatch n'est pas seulement du bruit ou un probleme de codes communaux non relies."
            ),
        )
    return (
        (
            f"This recent case combines `{counts['active_communes']:,}` active communes and `{counts['mismatch_communes']:,}` disagreement communes. `jrc_only` dominates in {jrc_top}, but Gaspar-only pockets remain visible in {gaspar_top}. "
            f"Public sources clearly confirm the 17-20 May 2024 flood episode in Moselle and northern Alsace. It is also plausible that some of the remaining mismatch reflects administrative timing lag at the end of the 2015-2024 source horizon; that lag explanation is an inference from the timing context, not a direct measurement from the comparison tables."
        ),
        (
            f"Ce cas recent combine `{counts['active_communes']:,}` communes actives et `{counts['mismatch_communes']:,}` communes en desacord. `jrc_only` domine dans {jrc_top}, mais des poches Gaspar-only restent visibles dans {gaspar_top}. "
            f"Les sources publiques confirment clairement l'episode d'inondation du 17 au 20 mai 2024 en Moselle et dans le nord de l'Alsace. Il est aussi plausible qu'une partie du mismatch residuel reflete un decalage temporel administratif en fin d'horizon 2015-2024 ; cette explication par le decalage est une inference de contexte, pas une mesure directe issue des tables de comparaison."
        ),
    )


def build_manual_section_en(example_results: list[dict[str, object]]) -> str:
    lines = [
        "## 4. Extended Manual Checks Across 2015-2024",
        "",
        "The manual examples below were selected to cover different mismatch profiles across the whole horizon:",
        "",
        "- a major Gaspar-dominant flood family (`Centre-Val de Loire, 2016-Q2`)",
        "- the two strongest JRC-dominant winter-flood corridors (`Grand Est, 2018-Q1` and `Bourgogne-Franche-Comte, 2018-Q1`)",
        "- a mixed case with public evidence on both sides (`Grand Est, 2021-Q3`)",
        "- a recent end-of-horizon case where both flood reality and timing effects matter (`Grand Est, 2024-Q2`)",
        "",
    ]
    for item in example_results:
        lines.extend(
            [
                f"### {item['title_en']}",
                "",
                f"- Quarter: `{item['period_label']}`",
                f"- Exact window: `{item['quarter_start']}` to `{item['quarter_end']}`",
                f"- Region code: `{item['region_code']}` ({item['region_name']})",
                f"- Active communes: `{item['active_communes']}`",
                f"- Both: `{item['both']}`",
                f"- Gaspar only: `{item['gaspar_only']}`",
                f"- JRC only: `{item['jrc_only']}`",
                f"- Overlap share: `{item['overlap_share']}`",
                f"- Top `gaspar_only` departments in this example: {item['gaspar_only_departments']}",
                f"- Top `jrc_only` departments in this example: {item['jrc_only_departments']}",
                f"- Why this case was selected: {item['selection_reason_en']}",
                "",
                f"![{item['title_en']} comparison map](assets/gaspar_jrc_horizon_audit/{item['image_name']})",
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
            "## 5. Why The Match Rate Stays Low",
            "",
            "- `Gaspar` and `JRC` do not encode the same object. Gaspar is an administrative recognition system, while JRC is a flood-footprint system derived from satellite products and related processing.",
            "- A large flood can fragment differently across the two sources in both space and time.",
            "- The region-quarter ranking shows that the mismatch is not confined to one famous event. It reappears in different hydrologic contexts: the late-May / early-June 2016 floods, the winter 2018 flood family, the July 2021 northeast floods, and the May 2024 Grand Est floods.",
            "- The department-level event match is much higher than the commune-level event match, which means that a large share of the disagreement comes from fine-grained commune allocation and timing segmentation.",
            "- The 2024 case also suggests that end-of-horizon administrative timing may amplify the mismatch in some recent quarters. This is an inference from the source horizon and the CatNat process, not a direct measurement from the overlap tables.",
            "",
            "## 6. Main Conclusion",
            "",
            "The low national Gaspar/JRC match rate is real, and the extended manual checks show that it persists across multiple important flood families between 2015 and 2024. The evidence is most consistent with a combination of different event concepts, different spatial footprints, commune-level fragmentation, and in some recent quarters possibly administrative timing lag as well.",
        ]
    )
    return "\n".join(lines)


def build_manual_section_fr(example_results: list[dict[str, object]]) -> str:
    lines = [
        "## 4. Verifications manuelles etendues sur 2015-2024",
        "",
        "Les exemples manuels ci-dessous ont ete choisis pour couvrir plusieurs profils de mismatch sur tout l'horizon :",
        "",
        "- une grande famille de crues dominee par Gaspar (`Centre-Val de Loire, 2016-T2`)",
        "- les deux couloirs de crues hivernales les plus domines par JRC (`Grand Est, 2018-T1` et `Bourgogne-Franche-Comte, 2018-T1`)",
        "- un cas mixte avec des preuves publiques des deux cotes (`Grand Est, 2021-T3`)",
        "- un cas recent en fin d'horizon ou la realite de la crue et les effets de timing peuvent tous deux compter (`Grand Est, 2024-T2`)",
        "",
    ]
    for item in example_results:
        lines.extend(
            [
                f"### {item['title_fr']}",
                "",
                f"- Trimestre: `{item['period_label']}`",
                f"- Fenetre exacte: `{item['quarter_start']}` a `{item['quarter_end']}`",
                f"- Code region: `{item['region_code']}` ({item['region_name']})",
                f"- Communes actives: `{item['active_communes']}`",
                f"- Les deux: `{item['both']}`",
                f"- Gaspar seulement: `{item['gaspar_only']}`",
                f"- JRC seulement: `{item['jrc_only']}`",
                f"- Part de recouvrement: `{item['overlap_share']}`",
                f"- Principaux departements `gaspar_only` dans cet exemple: {item['gaspar_only_departments']}",
                f"- Principaux departements `jrc_only` dans cet exemple: {item['jrc_only_departments']}",
                f"- Pourquoi ce cas a ete retenu: {item['selection_reason_fr']}",
                "",
                f"![{item['title_fr']} carte de comparaison](assets/gaspar_jrc_horizon_audit/{item['image_name']})",
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
            "## 5. Pourquoi le taux de match reste faible",
            "",
            "- `Gaspar` et `JRC` n'encodent pas le meme objet. Gaspar est un systeme de reconnaissance administrative, alors que JRC est un systeme d'emprise d'inondation derive de produits satellitaires et de leur traitement.",
            "- Une grande crue peut etre fragmentee differemment dans les deux sources, a la fois dans l'espace et dans le temps.",
            "- Le classement region-trimestre montre que le mismatch ne se limite pas a un seul evenement celebre. Il reapparait dans plusieurs contextes hydrologiques differents : les crues de fin mai / debut juin 2016, la famille de crues hivernales 2018, les inondations du nord-est en juillet 2021 et les inondations du Grand Est en mai 2024.",
            "- Le taux de match evenementiel au niveau departemental est bien plus eleve que le taux de match au niveau communal, ce qui signifie qu'une grande partie du desacord vient de l'allocation fine des communes et de la segmentation temporelle.",
            "- Le cas 2024 suggere aussi qu'un timing administratif de fin d'horizon peut amplifier le mismatch sur certains trimestres recents. C'est une inference tiree de l'horizon des sources et du processus CatNat, pas une mesure directe des tables de recouvrement.",
            "",
            "## 6. Conclusion principale",
            "",
            "Le faible taux de match national entre Gaspar et JRC est bien reel, et les verifications manuelles etendues montrent qu'il persiste sur plusieurs familles importantes d'inondations entre 2015 et 2024. Les elements reunis sont surtout coherents avec une combinaison de concepts d'evenements differents, d'emprises spatiales differentes, de fragmentation au niveau communal et, sur certains trimestres recents, possiblement d'un decalage temporel administratif.",
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
    ranking = compute_region_quarter_ranking(
        gaspar_rows=gaspar_rows,
        jrc_rows=jrc_rows,
        communes=communes,
    )
    ranking_export = ranking[
        [
            "region_code",
            "region_name",
            "year",
            "quarter",
            "period_label",
            "active_communes",
            "both",
            "gaspar_only",
            "jrc_only",
            "mismatch_communes",
            "overlap_share",
            "gaspar_share",
            "jrc_share",
            "dominant_source",
        ]
    ].copy()
    ranking_export.to_csv(RANKING_CSV, index=False)

    example_results: list[dict[str, object]] = []
    for case in build_horizon_cases():
        region_gdf, counts, dept_breakdown = build_example_activity(
            gaspar_rows=gaspar_rows,
            jrc_rows=jrc_rows,
            communes=communes,
            region_code=case.region_code,
            year=case.year,
            quarter=case.quarter,
        )
        quarter_start, quarter_end, period_label = quarter_period(case.year, case.quarter)
        image_name = f"{case.slug}.png"
        save_example_map(
            region_gdf=region_gdf,
            counts=counts,
            title=case.title_en,
            out_path=ASSET_DIR / image_name,
        )

        counts_with_mismatch = counts | {"mismatch_communes": counts["gaspar_only"] + counts["jrc_only"]}
        gaspar_top = top_departments_text(dept_breakdown, "gaspar_only")
        jrc_top = top_departments_text(dept_breakdown, "jrc_only")
        interpretation_en, interpretation_fr = build_case_interpretation(
            case,
            gaspar_top=gaspar_top,
            jrc_top=jrc_top,
            counts=counts_with_mismatch,
        )

        example_results.append(
            {
                "title_en": case.title_en,
                "title_fr": case.title_fr,
                "region_code": case.region_code,
                "region_name": REGION_NAMES.get(case.region_code, case.region_code),
                "period_label": period_label,
                "quarter_start": quarter_start.date().isoformat(),
                "quarter_end": quarter_end.date().isoformat(),
                "image_name": image_name,
                "selection_reason_en": case.selection_reason_en,
                "selection_reason_fr": case.selection_reason_fr,
                "interpretation_en": interpretation_en,
                "interpretation_fr": interpretation_fr,
                "evidence_links": case.evidence_links,
                "active_communes": int_str(counts["active_communes"]),
                "both": int_str(counts["both"]),
                "gaspar_only": int_str(counts["gaspar_only"]),
                "jrc_only": int_str(counts["jrc_only"]),
                "overlap_share": pct(counts["both"] / counts["active_communes"]) if counts["active_communes"] else "0.0%",
                "gaspar_only_departments": gaspar_top,
                "jrc_only_departments": jrc_top,
            }
        )

    en_content = "\n\n".join(
        [
            "# Gaspar vs JRC in France: 2015-2024 Horizon Audit",
            "",
            "This note extends the earlier manual-check report and documents two things:",
            "",
            "1. the overall national match statistics already produced by the project",
            "2. a deeper manual review of the periods where Gaspar and JRC differ the most across the `2015-2024` horizon",
            "",
            "This report can be regenerated with [src/build_gaspar_jrc_horizon_audit_docs.py](/D:/M2_MoSEF/DataCollection/src/build_gaspar_jrc_horizon_audit_docs.py).",
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
            build_period_ranking_section_en(ranking),
            build_notable_periods_section_en(ranking),
            build_manual_section_en(example_results),
        ]
    )

    fr_content = "\n\n".join(
        [
            "# Gaspar vs JRC en France : audit sur l'horizon 2015-2024",
            "",
            "Cette note prolonge le rapport precedent de verifications manuelles et documente deux choses :",
            "",
            "1. les statistiques nationales d'ensemble deja produites par le projet",
            "2. une revue manuelle plus approfondie des periodes ou Gaspar et JRC different le plus sur l'horizon `2015-2024`",
            "",
            "Ce rapport peut etre regenere avec [src/build_gaspar_jrc_horizon_audit_docs.py](/D:/M2_MoSEF/DataCollection/src/build_gaspar_jrc_horizon_audit_docs.py).",
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
            build_period_ranking_section_fr(ranking),
            build_notable_periods_section_fr(ranking),
            build_manual_section_fr(example_results),
        ]
    )

    en_content = re.sub(r"\n{3,}", "\n\n", en_content).strip() + "\n"
    fr_content = re.sub(r"\n{3,}", "\n\n", fr_content).strip() + "\n"

    EN_DOC.write_text(en_content, encoding="utf-8")
    FR_DOC.write_text(fr_content, encoding="utf-8")


def main() -> None:
    render_reports()
    print(f"Wrote {EN_DOC}")
    print(f"Wrote {FR_DOC}")
    print(f"Wrote ranking CSV {RANKING_CSV}")
    print(f"Wrote assets under {ASSET_DIR}")


if __name__ == "__main__":
    main()
