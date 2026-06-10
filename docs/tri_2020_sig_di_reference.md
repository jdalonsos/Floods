# Reference: TRI And Riparian Inputs Used By The Current Flood Workflow

This document explains the exact TRI and riparian files used today by `src/check_points_against_jrc_floods.py`.

It is written for the current simplified workflow only. It does not describe the older experimental `high / medium / low` TRI logic anymore.

## 1. Current Scope

The script currently produces two flood workbooks:

- `data/processed/T20_Anonymised_jrc_flood_check.xlsx`
- `data/processed/T20_Anonymised_gaspar_check.xlsx`

The spatial logic is split in two branches:

- JRC branch:
  direct raster confirmation around each point using the JRC TIFFs.
- Gaspar branch:
  commune-level and date-filtered Gaspar events are kept only if the point passes the simplified `TRI For / n_tri / riparian` rule.

This document is about the second branch only:

1. If the point is inside a `TRI For` polygon, keep the Gaspar flood.
2. If the point is not inside `TRI For` but is inside `n_tri`, reject the Gaspar flood.
3. If the point is outside `n_tri`, check riparian polygons.
4. If the point is inside riparian, keep the Gaspar flood.
5. Otherwise reject the Gaspar flood.

## 2. What `tri_2020_sig_di` Is

`data/raw/tri_2020_sig_di` is the unpacked French national TRI delivery.

TRI means `Territoires a Risques Importants d'Inondation`.

Official references:

- Georisques dataset page: [Zonages Inondation - Rapportage 2020](https://georisques.gouv.fr/donnees/bases-de-donnees/zonages-inondation-rapportage-2020)
- COVADIS standard: [Directive inondation v2.0 PDF](https://www.geoinformations.developpement-durable.gouv.fr/fichier/pdf/covadis_standard_di_v2-0_cle542659.pdf?arg=177835223&cle=d88321754f864921a3b18a4e6de399dd5e5fc3a9&file=pdf%2Fcovadis_standard_di_v2-0_cle542659.pdf)

The full folder contains many GIS layers, but the repository now keeps only the small subset required by the current Gaspar spatial rule.

## 3. Exact TRI Files Used

Only these four TRI shapefile stems are used by the current code:

| Layer stem | Why it is used |
| --- | --- |
| `n_inondable_01_01for_s` | River-overflow `For` polygons. |
| `n_inondable_02_01for_s` | Runoff `For` polygons. |
| `n_inondable_03_01for_s` | Marine-submersion `For` polygons. |
| `n_tri_s` | TRI territory boundaries used to distinguish `inside n_tri but not For` from `outside n_tri`. |

Tracked files currently present in Git for the TRI subset:

- `data/raw/tri_2020_sig_di/n_inondable_01_01for_s.dbf`
- `data/raw/tri_2020_sig_di/n_inondable_01_01for_s.prj`
- `data/raw/tri_2020_sig_di/n_inondable_01_01for_s.shp`
- `data/raw/tri_2020_sig_di/n_inondable_01_01for_s.shx`
- `data/raw/tri_2020_sig_di/n_inondable_02_01for_s.dbf`
- `data/raw/tri_2020_sig_di/n_inondable_02_01for_s.prj`
- `data/raw/tri_2020_sig_di/n_inondable_02_01for_s.shp`
- `data/raw/tri_2020_sig_di/n_inondable_02_01for_s.shx`
- `data/raw/tri_2020_sig_di/n_inondable_03_01for_s.dbf`
- `data/raw/tri_2020_sig_di/n_inondable_03_01for_s.prj`
- `data/raw/tri_2020_sig_di/n_inondable_03_01for_s.shp`
- `data/raw/tri_2020_sig_di/n_inondable_03_01for_s.shx`
- `data/raw/tri_2020_sig_di/n_tri_s.dbf`
- `data/raw/tri_2020_sig_di/n_tri_s.prj`
- `data/raw/tri_2020_sig_di/n_tri_s.shp`
- `data/raw/tri_2020_sig_di/n_tri_s.shx`

## 4. Why These TRI Files Are Enough

The current Gaspar branch does not need:

- medium TRI
- low TRI
- climate-change TRI variants
- water-depth classes
- velocity layers
- support layers

It only needs point-level answers to two questions:

1. Is the point inside one of the plain `For` floodable polygons?
2. If not, is the point still inside the broader TRI territory?

That is exactly why the current code uses:

- the three `For` polygon layers from `n_inondable_*`
- the boundary layer `n_tri_s`

Nothing else in the TRI archive changes the current `Gaspar -> keep or reject` decision.

## 5. How To Read The Kept TRI Filenames

Example:

```text
n_inondable_01_01for_s
```

Meaning:

- `n`: national delivery prefix
- `inondable`: floodable-surface family
- first `01`: flood type code
- second `01for`: scenario code
- `_s`: polygon geometry

For the local French delivery, the first code means:

| First code | Meaning |
| --- | --- |
| `01` | River overflow |
| `02` | Runoff |
| `03` | Marine submersion |

The second code used here is always `01For`, which is the plain `For` scenario kept by the repository.

So the three kept `For` layers mean:

- `n_inondable_01_01for_s`: river-overflow `For`
- `n_inondable_02_01for_s`: runoff `For`
- `n_inondable_03_01for_s`: marine-submersion `For`

## 6. Required Shapefile Components

For each kept shapefile stem, the workflow needs:

- `.shp`
- `.shx`
- `.dbf`
- `.prj`

Optional:

- `.qix`

What each component does:

- `.shp`: polygon geometry
- `.shx`: geometry index
- `.dbf`: attribute table
- `.prj`: CRS definition
- `.qix`: optional spatial index for faster reads

In practice, one logical layer such as `n_inondable_01_01for_s` is really a group of files that must stay together.

## 7. TRI Files Explicitly Not Used

The repository intentionally does not use:

- `n_inondable_*02moy*`
- `n_inondable_*03mcc*`
- `n_inondable_*03mcc_ct*`
- `n_inondable_*04fai*`
- `n_inondable_*04faicc_ct*`
- `n_inondable_*01forcc_ct*`
- `n_inondable_*01forcc_100*`
- all `n_iso_*` layers
- `n_soust_inond_s`
- `n_suralea_s`
- `n_ecoul_s`
- `n_champ_vit_p`
- `n_enjeu_*`
- `n_commune_s`
- `n_ouv_protec_l`
- other cartographic support layers

Reason:

- they are not needed by the current `For / n_tri / riparian` rule
- keeping them in Git would only increase payload size and complexity

## 8. Exact Riparian Files Used From The Copernicus Delivery

The riparian fallback is read from:

- `data/raw/France_Riparian`

The current code scans only shapefiles matching:

```text
France_Riparian/**/Data/rpz_*.shp
```

So the workflow is not reading the whole Copernicus package. It is reading only the final riparian polygon shapefiles inside the `Data/` folders.

Tracked riparian shapefile sets currently present in Git:

### 8.1 `DU006A`

- `data/raw/France_Riparian/rpz_DU006A_2018/rpz_DU006A/Data/rpz_DU006A.dbf`
- `data/raw/France_Riparian/rpz_DU006A_2018/rpz_DU006A/Data/rpz_DU006A.prj`
- `data/raw/France_Riparian/rpz_DU006A_2018/rpz_DU006A/Data/rpz_DU006A.shp`
- `data/raw/France_Riparian/rpz_DU006A_2018/rpz_DU006A/Data/rpz_DU006A.shx`

### 8.2 `DU009A`

- `data/raw/France_Riparian/rpz_DU009A_2018/rpz_DU009A/Data/rpz_DU009A.dbf`
- `data/raw/France_Riparian/rpz_DU009A_2018/rpz_DU009A/Data/rpz_DU009A.prj`
- `data/raw/France_Riparian/rpz_DU009A_2018/rpz_DU009A/Data/rpz_DU009A.shp`
- `data/raw/France_Riparian/rpz_DU009A_2018/rpz_DU009A/Data/rpz_DU009A.shx`

### 8.3 `DU016A`

- `data/raw/France_Riparian/rpz_DU016A_2018/rpz_DU016A/Data/rpz_DU016A.dbf`
- `data/raw/France_Riparian/rpz_DU016A_2018/rpz_DU016A/Data/rpz_DU016A.prj`
- `data/raw/France_Riparian/rpz_DU016A_2018/rpz_DU016A/Data/rpz_DU016A.shp`
- `data/raw/France_Riparian/rpz_DU016A_2018/rpz_DU016A/Data/rpz_DU016A.shx`

### 8.4 `DU017A`

- `data/raw/France_Riparian/rpz_DU017A_2018/rpz_DU017A/Data/rpz_DU017A.dbf`
- `data/raw/France_Riparian/rpz_DU017A_2018/rpz_DU017A/Data/rpz_DU017A.prj`
- `data/raw/France_Riparian/rpz_DU017A_2018/rpz_DU017A/Data/rpz_DU017A.shp`
- `data/raw/France_Riparian/rpz_DU017A_2018/rpz_DU017A/Data/rpz_DU017A.shx`

### 8.5 `DU041A`

- `data/raw/France_Riparian/rpz_DU041A_2018/rpz_DU041A/Data/rpz_DU041A.dbf`
- `data/raw/France_Riparian/rpz_DU041A_2018/rpz_DU041A/Data/rpz_DU041A.prj`
- `data/raw/France_Riparian/rpz_DU041A_2018/rpz_DU041A/Data/rpz_DU041A.shp`
- `data/raw/France_Riparian/rpz_DU041A_2018/rpz_DU041A/Data/rpz_DU041A.shx`

### 8.6 `DU043A`

- `data/raw/France_Riparian/rpz_DU043A_2018/rpz_DU043A/Data/rpz_DU043A.dbf`
- `data/raw/France_Riparian/rpz_DU043A_2018/rpz_DU043A/Data/rpz_DU043A.prj`
- `data/raw/France_Riparian/rpz_DU043A_2018/rpz_DU043A/Data/rpz_DU043A.shp`
- `data/raw/France_Riparian/rpz_DU043A_2018/rpz_DU043A/Data/rpz_DU043A.shx`

These are the exact Copernicus-derived riparian polygon files used by the repository today.

## 9. Riparian Files Not Used

The current code does not use:

- zip archives
- metadata XML files
- symbology folders
- `.sbn`
- `.sbx`
- `.shp.xml`
- other optional sidecars

Only the shapefile components listed above are needed for the current fallback logic.

## 10. How The Code Loads TRI And Riparian

Relevant functions in `src/check_points_against_jrc_floods.py`:

- `list_tri_for_members()`
- `load_tri_polygon_members()`
- `list_riparian_shapefiles()`
- `load_riparian_polygons()`
- `classify_points_for_gaspar()`

The code behavior is:

1. Load the three `TRI For` polygon layers.
2. Load `n_tri_s`.
3. Find which points intersect `TRI For`.
4. For points not already in `TRI For`, check whether they intersect `n_tri_s`.
5. For points outside `n_tri_s`, load and test the riparian `rpz_*.shp` polygons.
6. Keep only Gaspar events for points in:
   - `TRI For`
   - or `outside n_tri` and `inside riparian`

The script stores the simplified result with:

- `tri_for_hit`
- `tri_boundary_hit`
- `tri_zone_status`
- `riparian_hit`
- `gaspar_hit_reason`

## 11. Bottom Line

Yes: the current workflow uses only a very small subset of the TRI and Copernicus riparian deliveries.

Exact rule:

- `TRI For` => keep the Gaspar flood
- `inside n_tri but not For` => reject it
- `outside n_tri and inside riparian` => keep it
- otherwise => reject it

Exact TRI subset:

- `n_inondable_01_01for_s`
- `n_inondable_02_01for_s`
- `n_inondable_03_01for_s`
- `n_tri_s`

Exact riparian subset:

- the six `rpz_*.shp` shapefile sets currently tracked under `data/raw/France_Riparian/**/Data/`

That is the full current spatial documentation for the simplified Gaspar branch.
