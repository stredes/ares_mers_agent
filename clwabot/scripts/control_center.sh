#!/usr/bin/env bash
set -euo pipefail

cd /home/stredesmers/.openclaw/workspace/clwabot
exec python3 -m clwabot.core.control_center "$@"
