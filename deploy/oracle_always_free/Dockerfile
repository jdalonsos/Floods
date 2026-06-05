FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal \
    GDAL_CONFIG=/usr/bin/gdal-config

COPY deploy/oracle_always_free/runtime-requirements.txt /tmp/runtime-requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r /tmp/runtime-requirements.txt

COPY src /app/src
COPY data/raw/adminexpress-cog-simpl-000-2025.gpkg /app/data/raw/adminexpress-cog-simpl-000-2025.gpkg
COPY data/raw/catnat_gaspar.csv /app/data/raw/catnat_gaspar.csv
COPY data/processed/Gaspar_2015_2024.xlsx /app/data/processed/Gaspar_2015_2024.xlsx
COPY data/processed/france_lau_insee_documentation/events_fr_insee_long.csv /app/data/processed/france_lau_insee_documentation/events_fr_insee_long.csv
COPY data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv /app/data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv
COPY data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv /app/data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv
COPY deploy/oracle_always_free/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY deploy/oracle_always_free/healthcheck.sh /usr/local/bin/healthcheck.sh

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
