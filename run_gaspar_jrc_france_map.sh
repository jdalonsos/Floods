#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ps1_path="$(cygpath -w "$script_dir/run_gaspar_jrc_france_map.ps1")"
port="8502"

if [[ $# -ge 1 ]]; then
  case "$1" in
    -Port|--port)
      if [[ $# -lt 2 ]]; then
        echo "Missing port value after $1" >&2
        exit 1
      fi
      port="$2"
      shift 2
      ;;
    *)
      port="$1"
      shift
      ;;
  esac
fi

if [[ $# -gt 0 ]]; then
  echo "Unexpected arguments: $*" >&2
  echo "Usage: bash run_gaspar_jrc_france_map.sh [PORT]" >&2
  echo "   or: bash run_gaspar_jrc_france_map.sh --port PORT" >&2
  echo "   or: bash run_gaspar_jrc_france_map.sh -Port PORT" >&2
  exit 1
fi

exec powershell.exe -ExecutionPolicy Bypass -File "$ps1_path" -Port "$port"
