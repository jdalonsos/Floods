#!/usr/bin/env bash
set -euo pipefail

STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

exec streamlit run /app/src/gaspar_jrc_france_map_app.py \
  --server.address=0.0.0.0 \
  --server.port="${STREAMLIT_PORT}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
