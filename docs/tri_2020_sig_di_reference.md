# Reference: `tri_2020_sig_di`

This document explains what the local folder `data/raw/tri_2020_sig_di` contains, which TRI files the repository actually uses, and why the other TRI layers are currently ignored.

It is written for the current BCEF point-screening workflow implemented in `src/check_points_against_jrc_floods.py`.

## 1. What `tri_2020_sig_di` is

The folder `data/raw/tri_2020_sig_di` is the unpacked national TRI delivery used by the French flood-risk workflow.

TRI stands for `Territoires a Risques Importants d'Inondation`.

Official references:

- Georisques dataset page: [Zonages Inondation - Rapportage 2020](https://georisques.gouv.fr/donnees/bases-de-donnees/zonages-inondation-rapportage-2020)
- Official data standard: [COVADIS Directive inondation v2.0 PDF](https://www.geoinformations.developpement-durable.gouv.fr/fichier/pdf/covadis_standard_di_v2-0_cle542659.pdf?arg=177835223&cle=d88321754f864921a3b18a4e6de399dd5e5fc3a9&file=pdf%2Fcovadis_standard_di_v2-0_cle542659.pdf)

The Georisques page describes the 2020 TRI delivery as a national shapefile archive containing:

- management zoning
- floodable-surface zoning
- water-depth zoning
- exposed-asset layers
- and related support layers

The COVADIS standard describes the common national structure used to build those TRI GIS layers.

## 2. What is inside the local folder

Local inventory on `2026-06-08`:

- `252` files total
- `50` shapefile stems
- about `10.745 GB` unpacked

At family level, the folder looks like this:

| Family prefix | Shapefile stems | Approx total size | Role in the TRI delivery |
| --- | ---: | ---: | --- |
| `n_inondable` | 14 | `1558.0 MB` | Floodable-surface polygons by scenario |
| `n_iso` | 16 | `8898.9 MB` | Water-depth / hydraulic representation layers |
| `n_enjeu` | 9 | `309.9 MB` | Exposed assets / stakes |
| `n_ecoul` | 1 | `93.3 MB` | Flow / velocity-related polygons |
| `n_soust` | 1 | `48.3 MB` | Zones removed from inundation representation |
| `n_commune` | 1 | `33.4 MB` | Communes intersecting TRI territories |
| `n_suralea` | 1 | `32.6 MB` | Sur-alea polygons |
| `n_tri` | 1 | `13.3 MB` | TRI territory boundaries |
| `n_ouv` | 1 | `6.5 MB` | Flood-protection works |
| `n_champ` | 1 | `4.1 MB` | Velocity field points |
| `n_carte` | 2 | `3.1 MB` | Cartographic footprints / report map layers |
| `n_cote` | 1 | `0.3 MB` | Velocity / level support points |
| `n_quartier` | 1 | `0.2 MB` | District / neighborhood support layer |

## 3. How to read the filenames

### 3.1 Geometry suffix

From local inspection of the shapefiles:

- `_s` = surface geometry (`Polygon` / `MultiPolygon`)
- `_l` = line geometry (`LineString`)
- `_p` = point geometry (`Point` / `MultiPoint`)

This matches the COVADIS naming convention.

### 3.2 Main family names

The most important families in this folder are:

- `n_inondable_*`: floodable-surface polygons
- `n_iso_ht_*`: water-depth classes with fields such as `ht_min` and `ht_max`
- `n_suralea_s`: sur-alea polygons
- `n_soust_inond_s`: zones soustraites a l'inondation
- `n_ecoul_s`: hydraulic-flow polygons
- `n_enjeu_*`: exposed assets / stakes
- `n_tri_s`: TRI territory boundaries
- `n_commune_s`: communes intersecting TRI

### 3.3 Scenario codes

The current repository interprets the delivered TRI scenario codes like this:

| Scenario code | Repo TRI class | Meaning used in the repo |
| --- | --- | --- |
| `01For` | `high` | High-probability flood scenario |
| `01Forcc_ct` | `high` | High-probability scenario with climate-change short-term suffix |
| `01Forcc_100` | `high` | High-probability scenario with climate-change long-horizon suffix |
| `02Moy` | `medium` | Medium-probability flood scenario |
| `03Mcc` | `medium` | Medium-probability scenario with climate-change suffix |
| `03Mcc_ct` | `medium` | Medium-probability scenario with climate-change short-term suffix |
| `04Fai` | `low` | Low-probability flood scenario |
| `04Faicc_ct` | `low` | Low-probability scenario with climate-change short-term suffix |
| `04Fai_100` | `low` | Low-probability scenario with climate-change long-horizon suffix |

Important note:

- `01For`, `02Moy`, and `04Fai` are directly aligned with the standard's strong / medium / low probability framing.
- The climate-change variants such as `Forcc` and `Mcc` come from the delivered 2020 layer names and scenario values.
- The current code supports a few scenario codes that do not appear in the unpacked national folder today, such as `01Forcc_100` and `04Fai_100`, so the mapping stays future-safe.

Also important:

- the first numeric block in filenames such as `n_inondable_01_01for_s` or `n_inondable_03_03mcc_s` is preserved exactly as delivered
- the current repository does **not** reinterpret that first block for business logic
- the workflow only uses the scenario code itself to classify `TRI = high / medium / low / out`

## 4. Which TRI files the repository actually uses

For the current BCEF combined JRC + Gaspar workflow, the code only reads the `n_inondable_*` family.

This happens in `src/check_points_against_jrc_floods.py`:

- `list_tri_inondable_members(...)` keeps only shapefiles whose names start with `n_inondable_`
- `classify_points_against_tri(...)` loads all those polygons and intersects them with the points
- the intersected scenario codes are then reduced to one output class per point: `high`, `medium`, `low`, or `out`

The exact layer stems used today are:

| Layer stem | Delivered scenario | Repo TRI class | Why we keep it |
| --- | --- | --- | --- |
| `n_inondable_01_01for_s` | `01For` | `high` | Floodable-surface extent for a high-probability scenario |
| `n_inondable_01_02moy_s` | `02Moy` | `medium` | Floodable-surface extent for a medium-probability scenario |
| `n_inondable_01_03mcc_s` | `03Mcc` | `medium` | Floodable-surface extent for a medium climate-change scenario |
| `n_inondable_01_04fai_s` | `04Fai` | `low` | Floodable-surface extent for a low-probability scenario |
| `n_inondable_02_01for_s` | `01For` | `high` | Additional delivered floodable-surface extent, same TRI class |
| `n_inondable_02_02moy_s` | `02Moy` | `medium` | Additional delivered floodable-surface extent, same TRI class |
| `n_inondable_02_04fai_s` | `04Fai` | `low` | Additional delivered floodable-surface extent, same TRI class |
| `n_inondable_03_01for_s` | `01For` | `high` | Additional delivered floodable-surface extent, same TRI class |
| `n_inondable_03_01forcc_ct_s` | `01Forcc_ct` | `high` | Climate-change high scenario extent |
| `n_inondable_03_02moy_s` | `02Moy` | `medium` | Additional delivered floodable-surface extent, same TRI class |
| `n_inondable_03_03mcc_ct_s` | `03Mcc_ct` | `medium` | Climate-change medium scenario extent |
| `n_inondable_03_03mcc_s` | `03Mcc` | `medium` | Medium climate-change scenario extent |
| `n_inondable_03_04fai_s` | `04Fai` | `low` | Additional delivered floodable-surface extent, same TRI class |
| `n_inondable_03_04faicc_ct_s` | `04Faicc_ct` | `low` | Climate-change low scenario extent |

### 4.1 Sidecar files that are also required

For each kept stem, the workflow needs:

- `.shp`
- `.shx`
- `.dbf`
- `.prj`

Optional:

- `.qix` is helpful for indexing, but the current workflow does not require it

What each file does:

- `.shp`: the main geometry file. This is where the polygon shapes themselves are stored.
- `.shx`: the geometry index file. It lets GIS readers jump to the right geometry records inside the `.shp`.
- `.dbf`: the attribute table. This is where non-geometric fields such as `scenario`, `id_tri`, `typ_inond`, and `cours_deau` are stored.
- `.prj`: the coordinate reference system definition. It tells the reader which map projection / CRS the layer uses so the geometries can be interpreted correctly.
- `.qix`: an optional spatial index. It can make spatial reads faster, but GeoPandas / GDAL can still read the layer without it.

In practical terms, one kept TRI layer such as `n_inondable_01_01for_s` is not just one file. It is one logical shapefile dataset made of several sidecar files:

- `n_inondable_01_01for_s.shp`: polygon coordinates
- `n_inondable_01_01for_s.shx`: geometry index
- `n_inondable_01_01for_s.dbf`: attribute table
- `n_inondable_01_01for_s.prj`: CRS definition
- `n_inondable_01_01for_s.qix`: optional spatial index

Why the workflow really needs all required sidecars:

- without `.shp`, there is no geometry to intersect with the points
- without `.dbf`, the code loses the `scenario` field used to classify `TRI = high / medium / low`
- without `.prj`, CRS handling becomes unreliable or ambiguous
- without `.shx`, many GIS readers will fail or behave badly when opening the shapefile

That is why the repository tracks only these extensions for the kept `n_inondable_*` stems.

### 4.2 Why this family is enough for the current workflow

The BCEF rule does not currently need detailed hydraulic metrics from TRI. It only needs a point-level answer to:

- is the point inside a TRI floodable polygon?
- if yes, is that polygon tied to a `high`, `medium`, or `low` scenario?

That is why `n_inondable_*` is the right family for the present logic:

- it is directly about floodable surfaces
- it already carries the scenario code in the `scenario` field
- it supports a simple point-in-polygon classification

## 5. How the repository uses those files in practice

At runtime, the current script does this:

1. Load all `n_inondable_*` members from `data/raw/tri_2020_sig_di`.
2. Read only the polygons inside the points' bounding box.
3. Spatially intersect point geometries with those polygons.
4. Collect all intersected TRI scenario codes per point.
5. Reduce those scenario codes to one output class:
   - `high`
   - `medium`
   - `low`
   - `out`
6. Write the result to the combined output workbook as:
   - `TRI`
   - `tri_scenario_codes`
   - `tri_scenario_labels`

The final BCEF flood flag then uses TRI this way:

- `flag_jrc = 1` if the point has a positive local JRC flood hit
- if `flag_jrc = 0`, Gaspar is checked at commune level and date overlap
- `flag_flood = 1` from the Gaspar branch only when `TRI = high`
- `TRI = medium`, `TRI = low`, and `TRI = out` keep the final fallback flag at `0`

## 6. Which TRI layers are intentionally not used

The workflow ignores most of the TRI folder on purpose.

### 6.1 `n_iso_ht_*`

Examples:

- `n_iso_ht_01_01for_s`
- `n_iso_ht_03_03mcc_s`

Why they are not used:

- they represent water-depth classes
- they carry `ht_min` and `ht_max`
- they are very large
- the BCEF rule currently does **not** need depth-band classification

If the business rule later needs "how deep is the flood at the point inside TRI?", this family would become relevant.

### 6.2 `n_soust_inond_s`

Why it is not used:

- the layer name is about zones removed from inundation representation, not riparian corridors
- earlier in the project it was tested as a possible proxy, but that interpretation was too weak
- the current code does **not** use any riparian fallback

So `n_soust_inond_s` is now explicitly excluded from the decision rule.

### 6.3 `n_suralea_s`

Why it is not used:

- this family represents sur-alea information
- the current BCEF rule does not contain a separate sur-alea branch
- using it would introduce additional business assumptions that are not validated yet

### 6.4 `n_ecoul_s` and `n_champ_vit_p`

Why they are not used:

- they are hydraulic flow / velocity support layers
- the current rule is about floodable extent class, not flow velocity

### 6.5 `n_enjeu_*`

Why they are not used:

- these are exposed-assets / stakes layers
- they are useful for vulnerability, risk, and impact analysis
- they are not needed to decide whether a point falls in a TRI floodable surface class

### 6.6 `n_tri_s`, `n_commune_s`, `n_quartier_s`, `n_carte_*`

Why they are not used:

- they are boundaries, support layers, or map/report framing layers
- the current workflow already has its own point geometry and commune matching logic
- they do not improve the final `TRI = high / medium / low / out` classification

### 6.7 `n_ouv_protec_l`

Why it is not used:

- it represents protection works
- the current BCEF rule does not model protection-state logic

## 7. Push strategy for this repository

The full unpacked TRI folder is too large to push as normal Git content.

Practical numbers:

- full unpacked folder: about `10.745 GB`
- subset actually used by the workflow: about `1.52 GB`

Even the used subset still contains several large binary files, so the repository uses:

- `.gitignore` to ignore the full TRI delivery except the kept `n_inondable_*` sidecars
- `.gitattributes` to send large `n_inondable_*` `.shp`, `.dbf`, and `.shx` files through Git LFS

Current repository policy:

- keep only the `n_inondable_*` stems needed by the workflow
- keep `.prj` in normal Git because it is tiny
- do not track the giant original `tri_2020_sig_di (1).zip`
- do not track the unused TRI families

## 8. Full shapefile stem list in the local folder

For completeness, the local unpacked folder currently contains these `50` shapefile stems:

### 8.1 Cartographic support

- `n_carte_inond_s`
- `n_carte_risq_s`

### 8.2 Velocity / hydraulic support

- `n_champ_vit_p`
- `n_cote_vit_deb_p`
- `n_ecoul_s`
- `n_iso_cote_l`
- `n_iso_deb_s`

### 8.3 Administrative / boundary support

- `n_commune_s`
- `n_quartier_s`
- `n_tri_s`

### 8.4 Exposed assets / stakes

- `n_enjeu_crise_l`
- `n_enjeu_crise_p`
- `n_enjeu_dce_s`
- `n_enjeu_eco_s`
- `n_enjeu_ied_p`
- `n_enjeu_ippc_p`
- `n_enjeu_patrim_p`
- `n_enjeu_patrim_s`
- `n_enjeu_steu_p`

### 8.5 Floodable surfaces used by the repo

- `n_inondable_01_01for_s`
- `n_inondable_01_02moy_s`
- `n_inondable_01_03mcc_s`
- `n_inondable_01_04fai_s`
- `n_inondable_02_01for_s`
- `n_inondable_02_02moy_s`
- `n_inondable_02_04fai_s`
- `n_inondable_03_01for_s`
- `n_inondable_03_01forcc_ct_s`
- `n_inondable_03_02moy_s`
- `n_inondable_03_03mcc_ct_s`
- `n_inondable_03_03mcc_s`
- `n_inondable_03_04fai_s`
- `n_inondable_03_04faicc_ct_s`

### 8.6 Water-depth classes not used by the repo

- `n_iso_ht_01_01for_s`
- `n_iso_ht_01_02moy_s`
- `n_iso_ht_01_03mcc_s`
- `n_iso_ht_01_04fai_s`
- `n_iso_ht_02_01for_s`
- `n_iso_ht_02_02moy_s`
- `n_iso_ht_02_04fai_s`
- `n_iso_ht_03_01for_s`
- `n_iso_ht_03_01forcc_ct_s`
- `n_iso_ht_03_02moy_s`
- `n_iso_ht_03_03mcc_ct_s`
- `n_iso_ht_03_03mcc_s`
- `n_iso_ht_03_04fai_s`
- `n_iso_ht_03_04faicc_ct_s`

### 8.7 Protection / over-hazard / removed-inundation support

- `n_ouv_protec_l`
- `n_soust_inond_s`
- `n_suralea_s`

## 9. Bottom line

For this repository, `tri_2020_sig_di` is a broad national TRI delivery, but the current BCEF logic uses only one narrow part of it:

- the `n_inondable_*` floodable-surface polygons

Everything else in the folder may still be scientifically useful, but it is outside the present point-level decision rule.
