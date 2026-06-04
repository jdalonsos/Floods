# Gaspar vs JRC en France : statistiques de match et verifications visuelles manuelles

Cette note documente deux choses :

1. les statistiques nationales de match a partir des sorties de comparaison deja presentes dans le projet

2. des verifications visuelles manuelles par trimestre et par region a partir de la logique de carte d'activite communale

Ce rapport peut etre regenere avec [src/build_gaspar_jrc_match_audit_docs.py](/D:/M2_MoSEF/DataCollection/src/build_gaspar_jrc_match_audit_docs.py).

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

## 2. Verifications manuelles

Ces verifications utilisent la logique d'activite communale de [src/france_commune_activity.py](/D:/M2_MoSEF/DataCollection/src/france_commune_activity.py) et le workflow cartographique de [src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py).

Distinction importante :

- les statistiques nationales ci-dessus sont des statistiques de paires d'evenements issues du script de comparaison flexible
- les cartes manuelles ci-dessous sont des cartes d'activite communale par recouvrement de periode

Les deux sections sont donc liees, mais elles ne mesurent pas exactement le meme objet.

### Grand Est, T3 2021

- Trimestre: `2021-Q3`
- Code region: `44` (Grand Est)
- Communes actives: `829`
- Les deux: `95`
- Gaspar seulement: `202`
- JRC seulement: `532`
- Principaux departements `gaspar_only` dans cet exemple: 54 (45), 55 (41), 52 (34), 57 (29)
- Principaux departements `jrc_only` dans cet exemple: 55 (104), 57 (85), 51 (78), 08 (70)

Il s'agit d'un exemple a fort impact en juillet 2021, avec de nombreuses communes dans les trois classes. C'est utile pour verifier si le mismatch vient d'une erreur de donnees ou d'une vraie difference de representation du meme episode de crue.

![Grand Est, T3 2021 carte de comparaison](assets/gaspar_jrc_match_audit/grand_est_2021_q3.png)

Interpretation :

Le mismatch n'est pas aleatoire. Les communes `jrc_only` se concentrent surtout dans les departements 55 (104), 57 (85), 51 (78), 08 (70), alors que les communes `gaspar_only` sont plus fortes dans 54 (45), 55 (41), 52 (34), 57 (29). Une zone de recouvrement existe, mais elle reste beaucoup plus petite que les deux amas specifiques a chaque source, ce qui suggere que les deux bases voient bien le meme grand episode d'inondation du nord-est avec des footprints communaux differents.

Sources publiques utilisees pour contextualiser ce cas :

- [L'Est Republicain, Bar-le-Duc under water, 15 July 2021](https://www.estrepublicain.fr/faits-divers-justice/2021/07/15/inondations-spectaculaires-a-bar-le-duc-la-ville-toute-une-journee-les-pieds-dans-l-eau)
- [Meuse prefecture, July 13-15 2021 flood procedure](https://www.meuse.gouv.fr/Politiques-publiques/Securite/Demande-de-catastrophes-naturelles-Inondations-du-13-au-15-juillet-2021)
- [Champagne FM, Asfeld pumping operations, 14 July 2021](https://www.champagnefm.com/news/a-deborde-56670)
- [Radio 8 Ardennes, flood situation update, 16 July 2021](https://radio8fm.com/infos/article/16614-Pluie_inondations_Point_de_situation_dans_les_Ardennes_ce_16_juillet_2021_a_19h00)
- [Reperes de crues, Vieux-les-Asfeld](https://www.reperesdecrues.developpement-durable.gouv.fr/site/sortie-du-village-en-direction-de-avaux)

### Bourgogne-Franche-Comte, T3 2021

- Trimestre: `2021-Q3`
- Code region: `27` (Bourgogne-Franche-Comte)
- Communes actives: `508`
- Les deux: `22`
- Gaspar seulement: `69`
- JRC seulement: `417`
- Principaux departements `gaspar_only` dans cet exemple: 39 (63), 71 (5), 21 (1)
- Principaux departements `jrc_only` dans cet exemple: 70 (153), 71 (102), 39 (68), 25 (63)

Cet exemple voisin de juillet 2021 est fortement domine par JRC, tout en gardant des poches Gaspar-only. Il est utile car les sources publiques montrent deja des impacts de crue a la fois du cote du Jura et du cote de la Haute-Saone.

![Bourgogne-Franche-Comte, T3 2021 carte de comparaison](assets/gaspar_jrc_match_audit/bourgogne_franche_comte_2021_q3.png)

Interpretation :

Ce cas est fortement domine par JRC. Les communes `jrc_only` se concentrent dans 70 (153), 71 (102), 39 (68), 25 (63), alors que le `gaspar_only` est presque entierement concentre dans 39 (63), 71 (5), 21 (1). Visuellement, JRC s'etale sur un couloir plus large que Gaspar, ce qui est coherent avec une emprise hydrologique ou de plaine inondable plus large que l'ensemble des communes entrees en reconnaissance administrative.

Sources publiques utilisees pour contextualiser ce cas :

- [Le Progres, Jura floods, 16 July 2021](https://www.leprogres.fr/environnement/2021/07/16/inondations-glissement-de-terrain-le-departement-prend-l-eau)
- [Le Progres, Jura floods, 17 July 2021](https://www.leprogres.fr/environnement/2021/07/17/inondations-trois-cents-appels-en-une-heure-trente)
- [Official Rhone-Mediterranee basin event report](https://www.auvergne-rhone-alpes.developpement-durable.gouv.fr/IMG/pdf/20240606-epri-bassinrm-receuil_evts.pdf)
- [Legifrance decree of 23 July 2021](https://www.legifrance.gouv.fr/jorf/id/JORFSCTA000043879099)
- [L'Est Republicain, Autet cleanup, 25 July 2021](https://www.estrepublicain.fr/environnement/2021/07/25/nettoyage-apres-l-invasion-d-eau)

### Centre-Val de Loire, T2 2016

- Trimestre: `2016-Q2`
- Code region: `24` (Centre-Val de Loire)
- Communes actives: `818`
- Les deux: `89`
- Gaspar seulement: `707`
- JRC seulement: `22`
- Principaux departements `gaspar_only` dans cet exemple: 45 (237), 41 (144), 36 (123), 18 (122)
- Principaux departements `jrc_only` dans cet exemple: 37 (20), 41 (2)

C'est un cas domine par Gaspar, lie aux grandes inondations de fin mai et debut juin 2016. C'est un contre-exemple utile car il montre que certains evenements officiellement reconnus a grande echelle gardent un match JRC faible au niveau communal.

![Centre-Val de Loire, T2 2016 carte de comparaison](assets/gaspar_jrc_match_audit/centre_val_de_loire_2016_q2.png)

Interpretation :

Ce cas est fortement domine par Gaspar. Les communes `gaspar_only` se concentrent dans 45 (237), 41 (144), 36 (123), 18 (122), alors que le petit reliquat `jrc_only` reste limite a 37 (20), 41 (2). La lecture visuelle est donc celle d'un evenement tres largement reconnu administrativement, alors que JRC ne recouvre qu'un sous-ensemble plus etroit des communes touchees.

Sources publiques utilisees pour contextualiser ce cas :

- [Centre-Val de Loire prefecture, regional floods page](https://www.prefectures-regions.gouv.fr/centre-val-de-loire/Actualites/Principales/Inondations-en-region-Centre-Val-de-Loire)
- [DREAL Centre-Val de Loire, return on late May / early June 2016 floods](https://www.centre-val-de-loire.developpement-durable.gouv.fr/retour-sur-les-crues-de-fin-mai-et-debut-juin-2016-a3155.html)
- [Ministry of the Interior, return-experience report on May-June 2016 floods](https://www.interieur.gouv.fr/documentation/rapports/inondations-de-mai-et-juin-2016-dans-bassins-moyens-de-seine-et-de-loire-retour-dexperience-16080-r.html)
- [Loiret department, remembrance page for May-June 2016 floods](https://www.loiret.fr/actualite/inondations-de-mai-juin-2016-le-loiret-se-souvient)

## 3. Pourquoi le taux de match est faible

- `Gaspar` et `JRC` ne partent pas du meme concept d'evenement. Gaspar est un systeme de reconnaissance administrative, alors que JRC est un systeme de footprint d'inondation derive de produits satellitaires.
- Un meme episode physique peut etre fragmente differemment dans les deux sources selon les communes et selon les dates.
- Le match communal est particulierement difficile, car une source peut reconnaitre du ruissellement, des coulees de boue ou des inondations urbaines localisees alors que l'autre capte une emprise plus large de plaine inondable.
- Les taux departementaux montrent qu'il existe bien un recouvrement, mais ce recouvrement devient beaucoup plus faible des que la comparaison est forcee au grain commune-evenement.
- La logique d'harmonisation communale de Gaspar compte, mais ce n'est pas l'explication principale ici. La part de lignes Gaspar non resolues dans l'application reste faible par rapport a l'ampleur du mismatch national.

## 4. Conclusion principale

Le faible taux de match national est bien reel dans les sorties du projet, et les verifications manuelles suggerent qu'il ne s'agit pas seulement d'un bug de nettoyage. Le desacord reflete surtout des differences de grain evenementiel, de fragmentation temporelle et de support spatial entre une base de reconnaissance administrative et un produit satellitaire d'emprise d'inondation.
