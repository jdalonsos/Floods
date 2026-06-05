#!/usr/bin/env bash
set -euo pipefail

STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

curl --fail --silent "http://127.0.0.1:${STREAMLIT_PORT}/_stcore/health" > /dev/null
