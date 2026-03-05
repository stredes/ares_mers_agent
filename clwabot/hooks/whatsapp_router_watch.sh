#!/usr/bin/env bash
set -uo pipefail

WORKSPACE="/home/stredesmers/.openclaw/workspace"
cd "$WORKSPACE"

# Refuerza PATH en systemd --user para evitar fallas intermitentes de node/openclaw.
export PATH="/home/stredesmers/.nvm/versions/node/v24.13.1/bin:/home/stredesmers/.npm-global/bin:${PATH}"

OPENCLAW_BIN="${OPENCLAW_BIN:-}"
if [[ -z "$OPENCLAW_BIN" ]]; then
  if command -v openclaw >/dev/null 2>&1; then
    OPENCLAW_BIN="$(command -v openclaw)"
  else
    OPENCLAW_BIN="/home/stredesmers/.npm-global/bin/openclaw"
  fi
fi

if [[ ! -x "$OPENCLAW_BIN" ]]; then
  echo "[whatsapp_router_watch.sh] openclaw no ejecutable: $OPENCLAW_BIN" >&2
  exit 1
fi

LOG_MAX_BYTES="${OPENCLAW_LOG_MAX_BYTES:-1000000}"

# OpenClaw valida maxBytes <= 1,000,000.
if [[ ! "$LOG_MAX_BYTES" =~ ^[0-9]+$ ]]; then
  LOG_MAX_BYTES="1000000"
fi
if (( LOG_MAX_BYTES > 1000000 )); then
  LOG_MAX_BYTES="1000000"
fi

RETRY_DELAY_SECONDS="${OPENCLAW_RETRY_DELAY_SECONDS:-1}"
if [[ ! "$RETRY_DELAY_SECONDS" =~ ^[0-9]+$ ]]; then
  RETRY_DELAY_SECONDS="1"
fi

while true; do
  echo "[whatsapp_router_watch.sh] iniciando stream logs.follow..." >&2
  "$OPENCLAW_BIN" logs --follow --max-bytes "$LOG_MAX_BYTES" | python3 -m clwabot.hooks.whatsapp_router_watch
  exit_code=$?
  echo "[whatsapp_router_watch.sh] stream finalizado (code=${exit_code}), reintentando en ${RETRY_DELAY_SECONDS}s..." >&2
  sleep "$RETRY_DELAY_SECONDS"
done
