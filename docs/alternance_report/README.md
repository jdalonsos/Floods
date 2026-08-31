# Rapport d'alternance DataCollection

Ce dossier contient trois éléments :

- `build_rapport_alternance.py` : génère le rapport Word complet.
- `build_note_synthese_alternance.py` : génère une note de synthèse en français au format MoSEF.
- `generate_figures_for_other_pc.py` : prépare les figures finales à partir des sorties disponibles sur votre autre PC.
- `generated_figures/` : dossier attendu par le builder pour remplacer automatiquement les placeholders.

## 1. Générer le rapport maintenant

Depuis la racine du dépôt :

```powershell
python docs\alternance_report\build_rapport_alternance.py
```

Le document est écrit dans :

- `docs/alternance_report/rapport_alternance_data_collection.docx`

## 1 bis. Générer la note de synthèse

Depuis la racine du dépôt :

```powershell
python docs\alternance_report\build_note_synthese_alternance.py
```

Le document est écrit dans :

- `docs/alternance_report/note_synthese_alternance_data_collection.docx`

Un contrôle de conformité des consignes MoSEF est aussi disponible dans :

- `docs/alternance_report/conformite_rapport_alternance_mosef.md`

## 2. Générer les figures finales sur l'autre PC

Exemple de commande :

```powershell
python docs\alternance_report\generate_figures_for_other_pc.py `
  --comparison-7d-dir "data\processed\jrc_gaspar_comparison_flexible_7d" `
  --comparison-30d-dir "data\processed\jrc_gaspar_comparison_flexible_30d" `
  --flood-lgd "france_t20=outputs\flood_lgd_export\T20_Anonymised_FLOOD_LGD.csv" `
  --flood-lgd "france_collateral=outputs\flood_lgd_export\my_collaterals_points_FLOOD_LGD.csv" `
  --flood-lgd "italy_t20=outputs\flood_lgd_export\T20_Anonymised_italy_FLOOD_LGD.csv" `
  --flood-lgd "italy_collateral=outputs\flood_lgd_export\my_italy_collaterals_points_FLOOD_LGD.csv" `
  --copy-figure "france_commune_app=D:\captures\france_commune_app.png" `
  --copy-figure "raster_dashboard=D:\captures\raster_dashboard.png" `
  --copy-figure "lgd_portfolio_results=D:\captures\lgd_portfolio_results.png" `
  --out-dir "docs\alternance_report\generated_figures"
```

Le script génère notamment :

- `generated_figures/jrc_gaspar_comparison_snapshot.png`
- `generated_figures/flood_lgd_source_mix_france_t20.png`
- `generated_figures/flood_lgd_source_mix_france_collateral.png`
- `generated_figures/flood_lgd_source_mix_italy_t20.png`
- `generated_figures/flood_lgd_source_mix_italy_collateral.png`
- `generated_figures/france_commune_app.png`
- `generated_figures/raster_dashboard.png`
- `generated_figures/lgd_portfolio_results.png`

Il écrit aussi un manifest :

- `generated_figures/figure_manifest.json`

## 3. Régénérer le rapport avec les figures finales

```powershell
python docs\alternance_report\build_rapport_alternance.py `
  --figures-dir "docs\alternance_report\generated_figures" `
  --period "à confirmer" `
  --tutor "à confirmer" `
  --manager "à confirmer"
```

## 4. Fichiers reconnus automatiquement

Si vous placez manuellement l'un des fichiers suivants dans `generated_figures/`, le rapport l'intègrera automatiquement :

- `france_commune_app.png`
- `raster_dashboard.png`
- `jrc_gaspar_comparison_snapshot.png`
- `italy_hazard_map.png`
- `flood_lgd_source_mix_france_t20.png`
- `lgd_portfolio_results.png`

Les autres visuels absents sont remplacés par des placeholders explicites.
