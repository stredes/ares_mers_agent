from __future__ import annotations

from pathlib import Path

import yaml

from .intent_router import Intent

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_PATH = BASE_DIR / "config" / "scripts.yaml"


def _load_scripts() -> dict:
    if not SCRIPTS_PATH.exists():
        return {}
    try:
        return yaml.safe_load(SCRIPTS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def pick_auto_reply(intent: Intent) -> str:
    scripts = _load_scripts().get("scripts", {})
    if intent == "support":
        return scripts.get("tech_help", "")
    if intent == "urgency":
        return scripts.get("urgent_case", "")
    if intent == "meeting":
        return scripts.get("meeting_request", "")
    if intent in {"sales", "personal", "general"}:
        return scripts.get("welcome_general", "") or scripts.get("auto_reply_default", "")
    return scripts.get("auto_reply_default", "")
