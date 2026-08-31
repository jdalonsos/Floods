#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MODE="${1:-direct}"

if [[ "${MODE}" != "direct" && "${MODE}" != "caddy" ]]; then
  echo "Unsupported mode: ${MODE}. Use 'direct' or 'caddy'."
  exit 1
fi

cd "${REPO_ROOT}"
git pull --ff-only

cd "${SCRIPT_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created ${SCRIPT_DIR}/.env from .env.example. Review it before exposing the app publicly."
fi

COMPOSE_ARGS=(-f compose.yaml)
if [[ "${MODE}" == "caddy" ]]; then
  COMPOSE_ARGS+=(-f compose.caddy.yaml)
fi

docker compose "${COMPOSE_ARGS[@]}" build --pull
docker compose "${COMPOSE_ARGS[@]}" up -d
docker compose "${COMPOSE_ARGS[@]}" ps
