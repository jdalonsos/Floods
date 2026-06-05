#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-direct}"

cd "${SCRIPT_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created ${SCRIPT_DIR}/.env from .env.example. Review it before exposing the app publicly."
fi

if [[ "${MODE}" != "direct" && "${MODE}" != "caddy" ]]; then
  echo "Unsupported mode: ${MODE}. Use 'direct' or 'caddy'."
  exit 1
fi

set -a
source .env
set +a

if [[ "${MODE}" == "caddy" ]]; then
  if [[ -z "${APP_DOMAIN:-}" || -z "${LE_EMAIL:-}" ]]; then
    echo "In caddy mode, set APP_DOMAIN and LE_EMAIL in ${SCRIPT_DIR}/.env before deploying."
    exit 1
  fi
fi

COMPOSE_ARGS=(-f compose.yaml)
if [[ "${MODE}" == "caddy" ]]; then
  COMPOSE_ARGS+=(-f compose.caddy.yaml)
fi

docker compose "${COMPOSE_ARGS[@]}" build --pull
docker compose "${COMPOSE_ARGS[@]}" up -d
docker compose "${COMPOSE_ARGS[@]}" ps

echo
if [[ "${MODE}" == "caddy" ]]; then
  echo "Deployment started with Caddy. Open https://${APP_DOMAIN} once DNS points to this VM."
else
  echo "Deployment started in direct mode. Open http://<your-vm-public-ip>:${HOST_PORT:-8501}"
fi
