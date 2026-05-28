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



####
Order
1_Gaspar_2015_2024_processing
2_granular_tabularization
3_france_lau_to_insee
4_compare_france_jrc_gaspar_flexible



##### For the flexible comparison Gaspar vs JRC
#For the 30-day run, use:
Python src/compare_france_jrc_gaspar_flexible.py \
  --jrc-file data/processed/france_lau_insee_documentation/events_fr_insee_long.csv \
  --gaspar-file data/processed/Gaspar_2015_2024.xlsx \
  --france-lookup-file data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv \
  --sheet-name Gaspar20152024FloodsClean \
  --date-window-days 30 \
  --out-dir data/processed/jrc_gaspar_comparison_flexible_30d



  #### Matching coordinates

  it uses these defaults from check_points_against_jrc_floods.py (line 691):

--points-file = data/raw/france_20_gps_google_maps.xlsx (line 21 (line 21))
--sheet-name = first sheet (None) (line 692 (line 692))
--latitude-col = Latitude (line 693 (line 693))
--longitude-col = Longitude (line 694 (line 694))
--point-id-col = # (line 695 (line 695))
--city-col = City (line 696 (line 696))
--lau-file = data/raw/LAU_RG_01M_2024_4326.gpkg (line 23 (line 23))
--lau-country-filter = FR (line 698 (line 698))
--events-file = data/processed/_outputs_eurostat_full/events_lau_long.parquet (line 22 (line 22))
--flood-dir = data/JRC_flood_depth_maps (line 24 (line 24))
--france-lookup-file = data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv (line 25 (line 25))
--study-start = none (line 702 (line 702))
--study-end = none (line 703 (line 703))
--buffer-km = 2.0 (line 704 (line 704))
--threshold-cm = 0.0 (line 705 (line 705))
--out-file = data/processed/france_points_jrc_flood_check.xlsx (line 26 (line 26))