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

### 3.3 Full filename anatomy

The kept TRI filenames are not random. They are structured.

Example:

```text
n_inondable_03_03mcc_s
```

This can be read as:

- `n`: national-layer naming prefix used in the TRI delivery
- `inondable`: floodable-surface family
- first `03`: flood type code, stored in the TRI attributes as `typ_inond`
- second `03mcc`: scenario code, stored in the TRI attributes as `scenario`
- final `_s`: surface geometry layer

So the general pattern is:

```text
n_inondable_[typ_inond]_[scenario]_s
```

Another example:

```text
n_inondable_01_01for_s
```

This means:

- floodable-surface polygons
- flood type `01`
- scenario `01For`
- polygon geometry

And:

```text
n_inondable_02_02moy_s
```

means:

- floodable-surface polygons
- flood type `02`
- scenario `02Moy`
- polygon geometry

Important point:

- the two code blocks do **not** mean the same thing
- the first block is about the **kind of flooding**
- the second block is about the **scenario / probability framing**

### 3.4 What the first code means: `typ_inond`

From the official TRI ArcGIS layer metadata, the `typ_inond` field is the flood-type code.

The delivered values used in this national folder align with:

| First code in filename | TRI field | Meaning |
| --- | --- | --- |
| `01` | `typ_inond = 01` | `debordement de cours d'eau` |
| `02` | `typ_inond = 02` | `ruissellement` |
| `03` | `typ_inond = 03` | `submersion marine` |

Official reference:

- [Zonages Inondation - Rapportage 2020 ArcGIS layers](https://services.arcgis.com/d3voDfTFbHOCRwVR/arcgis/rest/services/Zonages_Inondation___Rapportage_2020/FeatureServer/layers)

What that means in practice:

- `n_inondable_01_*` layers are river-overflow floodable surfaces
- `n_inondable_02_*` layers are runoff floodable surfaces
- `n_inondable_03_*` layers are marine-submersion floodable surfaces

Important nuance:

- in the unpacked `tri_2020_sig_di` folder we observed only `01`, `02`, and `03`
- we did **not** observe a `typ_inond = 04` value in this local delivery
- so the current documentation only explains the flood-type values that are actually present in your TRI source

### 3.5 Local evidence from the unpacked layers

The interpretation above is not based only on the filename. It is also confirmed by the actual attribute fields inside the local shapefiles.

Representative local examples:

| Local layer | `typ_inond` | `scenario` | Sample clue from attributes | Interpretation |
| --- | --- | --- | --- | --- |
| `n_inondable_01_01for_s` | `01` | `01For` | sample `cours_deau = Berre` | river-overflow type + high-probability scenario |
| `n_inondable_02_01for_s` | `02` | `01For` | `cours_deau` empty in sample | runoff type + high-probability scenario |
| `n_inondable_03_01for_s` | `03` | `01For` | sample `cours_deau = submar` | marine-submersion type + high-probability scenario |
| `n_inondable_03_03mcc_s` | `03` | `03Mcc` | sample `cours_deau = submar` | marine-submersion type + medium climate-change scenario |
| `n_inondable_03_01forcc_ct_s` | `03` | `01Forcc_ct` | TRI id contains `_SUBMAR` in the sample | marine-submersion type + high climate-change short-term scenario |

This local evidence matters because it shows that:

- the first code in the filename really does match the `typ_inond` field
- the second code really does match the `scenario` field
- the repository is not inventing this split; it is already present in the official TRI data model

### 3.6 What the second code means: `scenario`

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

### 3.7 Why filenames look repetitive, for example `01_01`, `01_02`, `03_03`

The repetition is expected because the two blocks describe different dimensions:

- first block = flood type
- second block = scenario

So:

- `01_01for` means flood type `01` with scenario `01For`
- `01_02moy` means flood type `01` with scenario `02Moy`
- `01_03mcc` means flood type `01` with scenario `03Mcc`
- `03_01for` means flood type `03` with scenario `01For`
- `03_03mcc` means flood type `03` with scenario `03Mcc`

This is why filenames can look like "double-coded" names:

- `01_01for`
- `01_02moy`
- `02_01for`
- `03_01for`

They are not duplicates. They are saying:

- what kind of flooding the layer represents
- under which scenario the floodable surface was produced

### 3.8 What the repository uses from that naming

The repository does **not** currently use both code blocks equally.

Current business behavior:

- the script reads all kept `n_inondable_*` layers
- it keeps the full TRI attributes available during loading
- but the final BCEF TRI class is driven by the **scenario block**
- the first flood-type block is currently **not** used in the final `flag_flood` decision

In other words:

- `01_01for`, `02_01for`, and `03_01for` all become `TRI = high` in the current repo logic
- because the repo groups them by scenario severity, not by flood type

Also important:

- the first numeric block in filenames such as `n_inondable_01_01for_s` or `n_inondable_03_03mcc_s` is preserved exactly as delivered
- the current repository does **not** reinterpret that first block for the final BCEF flag
- the workflow only uses the scenario code itself to classify `TRI = high / medium / low / out`

## 4. Which TRI files the repository actually uses

For the current BCEF combined JRC + Gaspar workflow, the repository now keeps only the TRI files required by the simplified final logic:

- `TRI For` polygons
- `n_tri` territory boundaries

In code terms, the current logic is:

- if a Gaspar point is inside `TRI For` -> keep the Gaspar flood hit
- if it is not inside `TRI For` but still inside `n_tri` -> do not keep the hit
- if it is outside `n_tri` -> check riparian polygons

So the repository does **not** need the medium, low, or climate-change TRI layers anymore.

The exact TRI layer stems kept for the current repository are:

| Layer stem | Delivered scenario | Why it is kept |
| --- | --- | --- |
| `n_inondable_01_01for_s` | `01For` | River-overflow `For` polygons |
| `n_inondable_02_01for_s` | `01For` | Runoff `For` polygons |
| `n_inondable_03_01for_s` | `01For` | Marine-submersion `For` polygons |
| `n_tri_s` | not a scenario layer | National TRI territory boundaries used to distinguish `inside n_tri but not For` from `outside n_tri` |

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
- `.dbf`: the attribute table. This is where non-geometric fields such as `scenario`, `id_tri`, `typ_inond`, and `cours_deau` are stored when they exist.
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
- without `.dbf`, the code loses the attributes used to identify `TRI For` layers and the `n_tri` boundaries
- without `.prj`, CRS handling becomes unreliable or ambiguous
- without `.shx`, many GIS readers will fail or behave badly when opening the shapefile

That is why the repository tracks only these extensions for the kept TRI stems.

### 4.2 Why this family is enough for the current workflow

The current BCEF rule does not currently need detailed hydraulic metrics from TRI. It only needs point-level answers to:

- is the point inside a plain `TRI For` polygon?
- if not, is the point still inside a `n_tri` territory boundary?

That is why the reduced TRI payload is enough for the present logic:

- the `n_inondable_*01for*` layers give the positive `TRI For` branch
- `n_tri_s` gives the `inside n_tri but not For` branch
- all other TRI scenario layers can stay local but do not need to be tracked in GitHub

### 4.3 Minimal riparian payload tracked with the workflow

The current Gaspar fallback also uses a small riparian payload under `data/raw/France_Riparian`.

The code does **not** need:

- the original `.zip` downloads
- metadata XML files
- symbology folders
- `.sbn`, `.sbx`, `.shp.xml`, or other optional sidecars

For the current workflow, the repository only needs the shapefile components:

- `.shp`
- `.shx`
- `.dbf`
- `.prj`

for the local `rpz_*` layers that currently exist in `France_Riparian/**/Data/`.

Local folders observed in the current workspace:

- `rpz_DU006A`
- `rpz_DU009A`
- `rpz_DU016A`
- `rpz_DU017A`
- `rpz_DU041A`
- `rpz_DU043A`

At runtime the script scans only `rpz_*.shp` files inside those `Data/` folders.

## 5. How the repository uses those files in practice

At runtime, the current script does this:

1. Load only the plain `01For` members from `data/raw/tri_2020_sig_di`.
2. Load `n_tri_s`.
3. Read only the polygons inside the points' bounding box.
4. Spatially intersect point geometries with those polygons.
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
- the current code now uses dedicated `France_Riparian/**/Data/rpz_*.shp` layers for riparian fallback instead

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
