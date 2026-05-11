python src/france_lau_to_insee.py \
  --tabular-file data/_outputs_eurostat_full/events_lau_long.csv \
  --lau data/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/NUTS_RG_01M_2024_4326.gpkg \
  --adminexpress data/adminexpress-cog-simpl-000-2025.gpkg \
  --commune-history data/insee_history/v_commune_depuis_1943.csv \
  --commune-movements data/insee_history/v_mvt_commune_2025.csv


##### For marching INSEE code

./.venv/Scripts/python.exe src/france_lau_to_insee.py \
  --tabular-file data/processed/_outputs_eurostat_full/events_lau_long.csv \
  --lau data/raw/LAU_RG_01M_2024_4326.gpkg \
  --nuts data/raw/NUTS_RG_01M_2024_4326.gpkg \
  --adminexpress data/raw/adminexpress-cog-simpl-000-2025.gpkg \
  --commune-history data/raw/insee_history/v_commune_depuis_1943.csv \
  --commune-movements data/raw/insee_history/v_mvt_commune_2025.csv \
  --out-dir data/processed/france_lau_insee_documentation
