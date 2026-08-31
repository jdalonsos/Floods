# Gaspar vs JRC en France : audit sur l'horizon 2015-2024

Cette note prolonge le rapport precedent de verifications manuelles et documente deux choses :

1. les statistiques nationales d'ensemble deja produites par le projet

2. une revue manuelle plus approfondie des periodes ou Gaspar et JRC different le plus sur l'horizon `2015-2024`

Ce rapport peut etre regenere avec [src/build_gaspar_jrc_horizon_audit_docs.py](/D:/M2_MoSEF/DataCollection/src/build_gaspar_jrc_horizon_audit_docs.py).

Inputs et logique du projet utilises ici :

- [src/compare_france_jrc_gaspar_flexible.py](/D:/M2_MoSEF/DataCollection/src/compare_france_jrc_gaspar_flexible.py)

- [src/france_commune_activity.py](/D:/M2_MoSEF/DataCollection/src/france_commune_activity.py)

- [src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py)

- `data/processed/jrc_gaspar_comparison_flexible_7d`

- `data/processed/jrc_gaspar_comparison_flexible_30d`

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
| 7 jours | 66 | 222 | 288 | 22.9% | 499 | 3,006 | 3,505 | 14.2% |
| 30 jours | 80 | 208 | 288 | 27.8% | 587 | 2,918 | 3,505 | 16.7% |

### Couverture nationale au niveau evenementiel, regle de match departementale

| Fenetre | JRC matches | JRC exclusifs | JRC total | Taux de match JRC | Gaspar matches | Gaspar exclusifs | Gaspar total | Taux de match Gaspar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 jours | 125 | 163 | 288 | 43.4% | 1,488 | 2,017 | 3,505 | 42.5% |
| 30 jours | 171 | 117 | 288 | 59.4% | 1,886 | 1,619 | 3,505 | 53.8% |

### Couverture nationale au niveau des lignes communales

| Fenetre | Lignes JRC matchees | Lignes JRC totales | Taux de match ligne JRC | Lignes Gaspar matchees | Lignes Gaspar totales | Taux de match ligne Gaspar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 jours | 2,501 | 64,327 | 3.9% | 1,983 | 19,217 | 10.3% |
| 30 jours | 3,080 | 64,327 | 4.8% | 2,204 | 19,217 | 11.5% |

### Lecture

- Le faible taux de match communal est confirme par les sorties du projet. Avec la regle stricte `7 jours`, seulement `22.9%` des evenements JRC et `14.2%` des groupes d'evenements Gaspar trouvent un partenaire au niveau communal.
- Meme avec la fenetre plus permissive `30 jours`, le taux de match au niveau communal reste faible : `27.8%` pour JRC et `16.7%` pour Gaspar.
- Le match departemental est nettement plus eleve, ce qui montre qu'une grande partie du desacord vient de la fragmentation a l'echelle communale plutot que d'une absence totale de recouvrement.
- Gaspar contient `164` identifiants de decret mais `3,505` groupes d'evenements dans la logique de comparaison ; cela montre deja qu'un meme decret administratif peut se decomposer en plusieurs groupes dates.

## 2. Periodes ou le mismatch manuel est le plus fort sur 2015-2024

Pour etendre les verifications manuelles au-dela des exemples 2021 deja documentes, j'ai classe chaque region-trimestre francaise de `2015-T1` a `2024-T4` avec la meme logique d'activite communale que celle utilisee dans l'application Streamlit.

Distinction importante :

- ce classement repose sur **l'activite communale par recouvrement de periode**
- ce n'est pas la meme chose que les **statistiques de paires d'evenements** du script de comparaison flexible

Le fichier de classement utilise ici est enregistre ici :

- [region_quarter_mismatch_2015_2024.csv](/D:/M2_MoSEF/DataCollection/docs/assets/gaspar_jrc_horizon_audit/region_quarter_mismatch_2015_2024.csv)

### Principaux couples region-trimestre par nombre de communes en desacord

| Periode | Region | Communes actives | Les deux | Gaspar seulement | JRC seulement | Communes en desacord | Part de recouvrement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-Q1 | Grand Est | 1,432 | 120 | 48 | 1,264 | 1,312 | 8.4% |
| 2024-Q1 | Grand Est | 1,255 | 8 | 23 | 1,224 | 1,247 | 0.6% |
| 2018-Q1 | Bourgogne-Franche-Comte | 1,247 | 120 | 64 | 1,063 | 1,127 | 9.6% |
| 2020-Q1 | Grand Est | 1,109 | 6 | 5 | 1,098 | 1,103 | 0.5% |
| 2021-Q1 | Grand Est | 1,101 | 0 | 0 | 1,101 | 1,101 | 0.0% |
| 2024-Q2 | Grand Est | 1,190 | 110 | 348 | 732 | 1,080 | 9.2% |
| 2019-Q4 | Grand Est | 994 | 0 | 0 | 994 | 994 | 0.0% |
| 2020-Q2 | Grand Est | 956 | 1 | 8 | 947 | 955 | 0.1% |
| 2023-Q4 | Grand Est | 882 | 3 | 15 | 864 | 879 | 0.3% |
| 2024-Q1 | Occitanie | 868 | 1 | 10 | 857 | 867 | 0.1% |
| 2024-Q2 | Occitanie | 843 | 6 | 23 | 814 | 837 | 0.7% |
| 2021-Q1 | Bourgogne-Franche-Comte | 746 | 0 | 3 | 743 | 746 | 0.0% |

### Periodes les plus dominees par Gaspar

| Periode | Region | Communes actives | Les deux | Gaspar seulement | JRC seulement | Communes en desacord | Part de recouvrement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2016-Q2 | Centre-Val de Loire | 818 | 89 | 707 | 22 | 729 | 10.9% |
| 2016-Q2 | Ile-de-France | 583 | 0 | 583 | 0 | 583 | 0.0% |
| 2018-Q2 | Nouvelle-Aquitaine | 637 | 34 | 410 | 193 | 603 | 5.3% |
| 2016-Q2 | Hauts-de-France | 366 | 0 | 363 | 3 | 366 | 0.0% |
| 2024-Q2 | Grand Est | 1,190 | 110 | 348 | 732 | 1,080 | 9.2% |
| 2016-Q2 | Grand Est | 332 | 0 | 315 | 17 | 332 | 0.0% |
| 2019-Q4 | Provence-Alpes-Cote d'Azur | 360 | 24 | 305 | 31 | 336 | 6.7% |
| 2023-Q4 | Hauts-de-France | 492 | 89 | 302 | 101 | 403 | 18.1% |

### Periodes les plus dominees par JRC

| Periode | Region | Communes actives | Les deux | Gaspar seulement | JRC seulement | Communes en desacord | Part de recouvrement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-Q1 | Grand Est | 1,432 | 120 | 48 | 1,264 | 1,312 | 8.4% |
| 2024-Q1 | Grand Est | 1,255 | 8 | 23 | 1,224 | 1,247 | 0.6% |
| 2021-Q1 | Grand Est | 1,101 | 0 | 0 | 1,101 | 1,101 | 0.0% |
| 2020-Q1 | Grand Est | 1,109 | 6 | 5 | 1,098 | 1,103 | 0.5% |
| 2018-Q1 | Bourgogne-Franche-Comte | 1,247 | 120 | 64 | 1,063 | 1,127 | 9.6% |
| 2019-Q4 | Grand Est | 994 | 0 | 0 | 994 | 994 | 0.0% |
| 2020-Q2 | Grand Est | 956 | 1 | 8 | 947 | 955 | 0.1% |
| 2023-Q4 | Grand Est | 882 | 3 | 15 | 864 | 879 | 0.3% |

### Lecture

- Les plus grands mismatch ne se concentrent pas sur une seule annee ; ils couvrent `2016`, `2018`, `2021` et `2024`.
- Le trimestre a forte activite le plus domine par Gaspar est `Centre-Val de Loire, 2016-T2`, suivi par `Ile-de-France, 2016-T2`.
- Les periodes les plus dominees par JRC se concentrent sur la famille de crues hivernales de 2018 (`Grand Est, 2018-T1` et `Bourgogne-Franche-Comte, 2018-T1`) ainsi que sur des trimestres recents du Grand Est et du sud-ouest en fin d'horizon des sources.
- Certains cas de `2024`, situes en fin d'horizon des donnees, peuvent etre plus sensibles a un decalage temporel administratif que les trimestres plus anciens. Ce point sur le decalage temporel est une inference basee sur la position de la periode dans l'horizon des sources et sur la procedure CatNat, pas une mesure directe issue des tables de comparaison.

## 3. Autres periodes importantes sur l'horizon 2015-2024

Les cinq cas cartographies ne racontent pas toute l'histoire. Le classement met aussi en evidence d'autres periodes d'inondation historiquement importantes qui aident a comprendre pourquoi le taux de match communal national reste faible.

### Ile-de-France, T2 2016

- Trimestre: `2016-Q2`
- Profil dans le classement: Tres grand trimestre domine par Gaspar, lie a la famille de crues Seine / Loing de fin mai et debut juin 2016.
- Communes actives: `583`
- Les deux: `0`
- Gaspar seulement: `583`
- JRC seulement: `0`
- Part de recouvrement: `0.0%`
- Pourquoi c'est important: Cette periode ne fait pas partie des cinq cas cartographies car elle appartient a la meme famille nationale de crues que Centre-Val de Loire 2016, mais elle confirme que le mismatch de 2016 depasse largement une seule region.

Liens de preuve :

- [DRIEAT Ile-de-France, one year after the May-June 2016 flood](https://www.drieat.ile-de-france.developpement-durable.gouv.fr/crue-de-mai-juin-2016-le-point-un-an-apres-r1507.html)
- [Ministry of the Interior, return-experience report on May-June 2016 floods](https://www.interieur.gouv.fr/documentation/rapports/inondations-de-mai-et-juin-2016-dans-bassins-moyens-de-seine-et-de-loire-retour-dexperience-16080-r.html)

### Provence-Alpes-Cote d'Azur, T4 2019

- Trimestre: `2019-Q4`
- Profil dans le classement: Trimestre fortement domine par Gaspar, lie aux inondations de novembre 2019 dans le Var et les Alpes-Maritimes.
- Communes actives: `360`
- Les deux: `24`
- Gaspar seulement: `305`
- JRC seulement: `31`
- Part de recouvrement: `6.7%`
- Pourquoi c'est important: Ce cas montre que le mismatch ne se limite ni au nord-est ni a 2016. Les episodes mediterraneens produisent eux aussi un fort desacord au niveau communal.

Liens de preuve :

- [Legifrance, CatNat recognition for the 22-24 November 2019 floods](https://www.legifrance.gouv.fr/jorf/article_jo/JORFARTI000041717653)
- [Official Rhone-Mediterranee flood-event report, Var floods of 22-24 November 2019](https://www.auvergne-rhone-alpes.developpement-durable.gouv.fr/IMG/pdf/20240606-epri-bassinrm-receuil_evts.pdf)

### Hauts-de-France, T4 2023

- Trimestre: `2023-Q4`
- Profil dans le classement: Trimestre fortement domine par Gaspar, lie aux inondations de novembre 2023 dans le Pas-de-Calais et le Nord.
- Communes actives: `492`
- Les deux: `89`
- Gaspar seulement: `302`
- JRC seulement: `101`
- Part de recouvrement: `18.1%`
- Pourquoi c'est important: Ce cas recent confirme que de grands episodes de crue peuvent rester fortement orientes vers Gaspar, meme lorsque les preuves publiques et la reponse nationale sont tres visibles.

Liens de preuve :

- [Hauts-de-France regional prefecture, flood situation update, 22 November 2023](https://www.prefectures-regions.gouv.fr/hauts-de-france/Actualites/Crues-dans-le-Pas-de-Calais-et-le-Nord-point-de-situation-sur-les-moyens-mobilises-au-22.11)
- [Service-Public, CatNat recognition for 205 communes after the November 2023 floods](https://www.service-public.gouv.fr/particuliers/actualites/A16928?lang=en)
- [info.gouv.fr, national government response to the Hauts-de-France floods](https://www.info.gouv.fr/actualite/le-gouvernement-se-mobilise-face-aux-inondations)

## 4. Verifications manuelles etendues sur 2015-2024

Les exemples manuels ci-dessous ont ete choisis pour couvrir plusieurs profils de mismatch sur tout l'horizon :

- une grande famille de crues dominee par Gaspar (`Centre-Val de Loire, 2016-T2`)
- les deux couloirs de crues hivernales les plus domines par JRC (`Grand Est, 2018-T1` et `Bourgogne-Franche-Comte, 2018-T1`)
- un cas mixte avec des preuves publiques des deux cotes (`Grand Est, 2021-T3`)
- un cas recent en fin d'horizon ou la realite de la crue et les effets de timing peuvent tous deux compter (`Grand Est, 2024-T2`)

### Centre-Val de Loire, T2 2016

- Trimestre: `2016-Q2`
- Fenetre exacte: `2016-04-01` a `2016-06-30`
- Code region: `24` (Centre-Val de Loire)
- Communes actives: `818`
- Les deux: `89`
- Gaspar seulement: `707`
- JRC seulement: `22`
- Part de recouvrement: `10.9%`
- Principaux departements `gaspar_only` dans cet exemple: 45 (237), 41 (144), 36 (123), 18 (122)
- Principaux departements `jrc_only` dans cet exemple: 37 (20), 41 (2)
- Pourquoi ce cas a ete retenu: Choisi comme le trimestre a forte activite le plus domine par Gaspar sur l'horizon 2015-2024.

![Centre-Val de Loire, T2 2016 carte de comparaison](assets/gaspar_jrc_horizon_audit/centre_val_de_loire_2016_q2.png)

Interpretation :

C'est le trimestre a forte activite le plus domine par Gaspar sur tout l'horizon. Les communes `gaspar_only` se concentrent dans 45 (237), 41 (144), 36 (123), 18 (122), alors que le petit reliquat `jrc_only` reste limite a 37 (20), 41 (2). Les sources externes confirment clairement un grand episode de crues entre fin mai et debut juin 2016 ; le faible recouvrement JRC se lit donc plutot comme une difference d'emprise et de timing que comme une absence d'inondation.

Sources publiques utilisees pour contextualiser ce cas :

- [Centre-Val de Loire prefecture, regional floods page](https://www.prefectures-regions.gouv.fr/centre-val-de-loire/Actualites/Principales/Inondations-en-region-Centre-Val-de-Loire)
- [DREAL Centre-Val de Loire, return on late May / early June 2016 floods](https://www.centre-val-de-loire.developpement-durable.gouv.fr/retour-sur-les-crues-de-fin-mai-et-debut-juin-2016-a3155.html)
- [Ministry of the Interior, return-experience report on May-June 2016 floods](https://www.interieur.gouv.fr/fr/Publications/Rapports-de-l-IGA/Securite-civile/Inondations-de-mai-et-de-juin-2016-dans-les-bassins-moyens-de-la-Seine-et-de-la-Loire-retour-d-experience)
- [Loiret department, remembrance page for May-June 2016 floods](https://www.loiret.fr/actualite/inondations-de-mai-juin-2016-le-loiret-se-souvient)

### Grand Est, T1 2018

- Trimestre: `2018-Q1`
- Fenetre exacte: `2018-01-01` a `2018-03-31`
- Code region: `44` (Grand Est)
- Communes actives: `1,432`
- Les deux: `120`
- Gaspar seulement: `48`
- JRC seulement: `1,264`
- Part de recouvrement: `8.4%`
- Principaux departements `gaspar_only` dans cet exemple: 10 (32), 88 (10), 51 (2), 52 (2)
- Principaux departements `jrc_only` dans cet exemple: 55 (205), 57 (203), 51 (145), 54 (141)
- Pourquoi ce cas a ete retenu: Choisi car il s'agit du plus grand mismatch region-trimestre de tout le classement 2015-2024.

![Grand Est, T1 2018 carte de comparaison](assets/gaspar_jrc_horizon_audit/grand_est_2018_q1.png)

Interpretation :

Il s'agit du plus grand mismatch region-trimestre de tout le classement. Les communes `jrc_only` se concentrent tres fortement dans 55 (205), 57 (203), 51 (145), 54 (141), alors que `gaspar_only` reste limite a 10 (32), 88 (10), 51 (2), 52 (2). Les sources hydrologiques officielles et les reperes de crues confirment des inondations generalisees en janvier 2018 sur le nord-est, ce qui est coherent avec un evenement hydrologique tres large dont l'emprise raster depasse nettement la zone de recouvrement administrative.

Sources publiques utilisees pour contextualiser ce cas :

- [Meteo-France, January 2018 remarkable floods](https://meteofrance.com/magazine/meteo-histoire/les-grands-evenements/janvier-2018-inondations-et-crues-remarquables)
- [Bas-Rhin prefecture, 2018 press archive with 23 January flood bulletin](https://www.bas-rhin.gouv.fr/Actualites/Communiques-Agenda/Archive-CP/Communiques-2018)
- [Reperes de crues, Moselle January 2018 flood mark near Metz](https://www.reperesdecrues.developpement-durable.gouv.fr/repere/metz-culee-amont-rive-gauche-du-pont-d153z-2eme-pont-en-aval-de-la-confluence-avec-la-seille)
- [Rhin-Meuse flood-risk plan, generalized January 2018 flood on Meuse and Rhine basins](https://www.grand-est.developpement-durable.gouv.fr/IMG/pdf/pgri-rhin-meuse_approuve.pdf)

### Bourgogne-Franche-Comte, T1 2018

- Trimestre: `2018-Q1`
- Fenetre exacte: `2018-01-01` a `2018-03-31`
- Code region: `27` (Bourgogne-Franche-Comte)
- Communes actives: `1,247`
- Les deux: `120`
- Gaspar seulement: `64`
- JRC seulement: `1,063`
- Part de recouvrement: `9.6%`
- Principaux departements `gaspar_only` dans cet exemple: 70 (18), 21 (16), 89 (14), 25 (8)
- Principaux departements `jrc_only` dans cet exemple: 70 (226), 71 (198), 21 (148), 25 (132)
- Pourquoi ce cas a ete retenu: Choisi comme deuxieme plus grand trimestre en mismatch et comme couloir voisin des crues hivernales du cas Grand Est 2018.

![Bourgogne-Franche-Comte, T1 2018 carte de comparaison](assets/gaspar_jrc_horizon_audit/bourgogne_franche_comte_2018_q1.png)

Interpretation :

Ce cas voisin de l'hiver 2018 est lui aussi fortement domine par JRC. Les communes `jrc_only` se concentrent dans 70 (226), 71 (198), 21 (148), 25 (132), alors que `gaspar_only` reste beaucoup plus reduit dans 70 (18), 21 (16), 89 (14), 25 (8). Le bulletin hydrologique regional et les alertes prefectorales confirment deux sequences de crues en janvier 2018 ; le motif ressemble donc encore a un couloir de crue tres large avec un recouvrement administratif limite.

Sources publiques utilisees pour contextualiser ce cas :

- [Bourgogne-Franche-Comte hydrological bulletin, special January 2018 flood issue](https://www.bourgogne-franche-comte.developpement-durable.gouv.fr/IMG/pdf/bull_bfc_01_2018_cle11613d.pdf)
- [Doubs prefecture, orange flood vigilance, 23 January 2018](https://www.doubs.gouv.fr/layout/set/print/Publications/Salle-de-Presse/Communiques-de-presse/Annee-2018/Le-Doubs-place-en-vigilance-orange-inondations)
- [Saone-et-Loire prefecture, orange flood vigilance point, 25 January 2018](https://www.saone-et-loire.gouv.fr/Actualites/Salle-de-presse/L-historique-des-annees-precedentes/2018/Janvier/Alerte-crues-vigilance-orange-en-Saone-et-Loire-point-de-situation)
- [Ministry of the Interior, late January 2018 floods and CatNat recognition](https://www.interieur.gouv.fr/archive/inondations-de-fin-janvier-2018-275-communes-reconnues-en-etat-de-catastrophe-naturelle)

### Grand Est, T3 2021

- Trimestre: `2021-Q3`
- Fenetre exacte: `2021-07-01` a `2021-09-30`
- Code region: `44` (Grand Est)
- Communes actives: `829`
- Les deux: `95`
- Gaspar seulement: `202`
- JRC seulement: `532`
- Part de recouvrement: `11.5%`
- Principaux departements `gaspar_only` dans cet exemple: 54 (45), 55 (41), 52 (34), 57 (29)
- Principaux departements `jrc_only` dans cet exemple: 55 (104), 57 (85), 51 (78), 08 (70)
- Pourquoi ce cas a ete retenu: Choisi comme cas mixte de juillet 2021, ou les clusters Gaspar-only et JRC-only sont tous deux soutenus par des sources publiques.

![Grand Est, T3 2021 carte de comparaison](assets/gaspar_jrc_horizon_audit/grand_est_2021_q3.png)

Interpretation :

Ce cas reste un cas mixte plutot qu'un extreme a source unique. Les communes `jrc_only` se concentrent surtout dans 55 (104), 57 (85), 51 (78), 08 (70), alors que les communes `gaspar_only` sont plus fortes dans 54 (45), 55 (41), 52 (34), 57 (29). Comme il existe des preuves publiques des deux cotes, cet exemple est particulierement utile pour montrer que le mismatch n'est pas seulement du bruit ou un probleme de codes communaux non relies.

Sources publiques utilisees pour contextualiser ce cas :

- [L'Est Republicain, Bar-le-Duc under water, 15 July 2021](https://www.estrepublicain.fr/faits-divers-justice/2021/07/15/inondations-spectaculaires-a-bar-le-duc-la-ville-toute-une-journee-les-pieds-dans-l-eau)
- [Meuse prefecture, July 13-15 2021 flood procedure](https://www.meuse.gouv.fr/Politiques-publiques/Securite/Demande-de-catastrophes-naturelles-Inondations-du-13-au-15-juillet-2021)
- [Champagne FM, Asfeld pumping operations, 14 July 2021](https://www.champagnefm.com/news/a-deborde-56670)
- [Radio 8 Ardennes, flood situation update, 16 July 2021](https://radio8fm.com/infos/article/16614-Pluie_inondations_Point_de_situation_dans_les_Ardennes_ce_16_juillet_2021_a_19h00)
- [Reperes de crues, Vieux-les-Asfeld](https://www.reperesdecrues.developpement-durable.gouv.fr/site/sortie-du-village-en-direction-de-avaux)

### Grand Est, T2 2024

- Trimestre: `2024-Q2`
- Fenetre exacte: `2024-04-01` a `2024-06-30`
- Code region: `44` (Grand Est)
- Communes actives: `1,190`
- Les deux: `110`
- Gaspar seulement: `348`
- JRC seulement: `732`
- Part de recouvrement: `9.2%`
- Principaux departements `gaspar_only` dans cet exemple: 57 (227), 67 (44), 52 (39), 54 (16)
- Principaux departements `jrc_only` dans cet exemple: 51 (186), 10 (156), 55 (106), 08 (70)
- Pourquoi ce cas a ete retenu: Choisi comme cas recent en fin d'horizon, avec un mismatch tres large et des preuves publiques claires autour des inondations du 17 au 20 mai 2024.

![Grand Est, T2 2024 carte de comparaison](assets/gaspar_jrc_horizon_audit/grand_est_2024_q2.png)

Interpretation :

Ce cas recent combine `1,190` communes actives et `1,080` communes en desacord. `jrc_only` domine dans 51 (186), 10 (156), 55 (106), 08 (70), mais des poches Gaspar-only restent visibles dans 57 (227), 67 (44), 52 (39), 54 (16). Les sources publiques confirment clairement l'episode d'inondation du 17 au 20 mai 2024 en Moselle et dans le nord de l'Alsace. Il est aussi plausible qu'une partie du mismatch residuel reflete un decalage temporel administratif en fin d'horizon 2015-2024 ; cette explication par le decalage est une inference de contexte, pas une mesure directe issue des tables de comparaison.

Sources publiques utilisees pour contextualiser ce cas :

- [Ecology ministry press release on Grand Est floods, 18 May 2024](https://www.ecologie.gouv.fr/presse/inondations-grand-est-christophe-bechu-appelle-vigilance-habitants-rappelle-bons)
- [Moselle prefecture, accelerated CatNat procedure for May 2024 floods](https://www.moselle.gouv.fr/Actualites/Securite/Protection-publique-et-securite-civile/Inondations-mai-2024-Procedure-de-reconnaissance-de-l-Etat-de-catastrophe-naturelle-acceleree)
- [DREAL Grand Est hydrological bulletin, May 2024](https://www.grand-est.developpement-durable.gouv.fr/bsh-grand-est-mai-2024-a22699.html)
- [Moselle state services, after-action note on the May 2024 floods](https://www.moselle.gouv.fr/Publications/Actu-Moselle-Le-magazine-de-l-Etat-en-Moselle/Annee-2024/La-lettre-des-services-de-l-Etat-en-Moselle-n-67/La-Moselle-frappee-par-les-inondations)

## 5. Pourquoi le taux de match reste faible

- `Gaspar` et `JRC` n'encodent pas le meme objet. Gaspar est un systeme de reconnaissance administrative, alors que JRC est un systeme d'emprise d'inondation derive de produits satellitaires et de leur traitement.
- Une grande crue peut etre fragmentee differemment dans les deux sources, a la fois dans l'espace et dans le temps.
- Le classement region-trimestre montre que le mismatch ne se limite pas a un seul evenement celebre. Il reapparait dans plusieurs contextes hydrologiques differents : les crues de fin mai / debut juin 2016, la famille de crues hivernales 2018, les inondations du nord-est en juillet 2021 et les inondations du Grand Est en mai 2024.
- Le taux de match evenementiel au niveau departemental est bien plus eleve que le taux de match au niveau communal, ce qui signifie qu'une grande partie du desacord vient de l'allocation fine des communes et de la segmentation temporelle.
- Le cas 2024 suggere aussi qu'un timing administratif de fin d'horizon peut amplifier le mismatch sur certains trimestres recents. C'est une inference tiree de l'horizon des sources et du processus CatNat, pas une mesure directe des tables de recouvrement.

## 6. Conclusion principale

Le faible taux de match national entre Gaspar et JRC est bien reel, et les verifications manuelles etendues montrent qu'il persiste sur plusieurs familles importantes d'inondations entre 2015 et 2024. Les elements reunis sont surtout coherents avec une combinaison de concepts d'evenements differents, d'emprises spatiales differentes, de fragmentation au niveau communal et, sur certains trimestres recents, possiblement d'un decalage temporel administratif.
