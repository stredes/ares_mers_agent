#!/usr/bin/env bash
set -euo pipefail

cd /home/stredesmers/.openclaw/workspace

NODE_BIN="/home/stredesmers/.nvm/versions/node/v24.13.1/bin/node"
OPENCLAW_MJS="/home/stredesmers/.npm-global/lib/node_modules/openclaw/openclaw.mjs"
PYTHON_BIN="/usr/bin/python3"

exec "$NODE_BIN" "$OPENCLAW_MJS" logs --follow | "$PYTHON_BIN" -m clwabot.hooks.whatsapp_router_watch
