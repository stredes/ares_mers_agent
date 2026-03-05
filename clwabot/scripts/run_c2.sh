#!/usr/bin/env bash
set -euo pipefail

# Ejecuta el C2 terminal reactivo (ASCII) en el host local del agente.
# Uso:
#   ./scripts/run_c2.sh
#   ./scripts/run_c2.sh --interval 1.5
#   ./scripts/run_c2.sh --gateway-host 127.0.0.1 --gateway-port 18789

REPO_DIR="/home/stredesmers/.openclaw/workspace/clwabot"
cd "$REPO_DIR"

export PYTHONPATH="${REPO_DIR}/..:${PYTHONPATH:-}"

exec python3 -m c2 "$@"
