from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "data" / "state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state() -> Dict[str, Any]:
    return {
        "vip": {"last_morning_sent": {}},
        "reports": {"last_daily_report": None, "last_weekly_report": None},
        "assistant": {
            "paused": False,
            "mode": "normal",  # normal | busy | vacation
            "business_hours": {"start": "09:00", "end": "19:00", "timezone": "America/Santiago"},
        },
        "contacts": {},
        "metrics": {"events": []},
    }


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return default_state()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default_state()

    merged = default_state()
    _deep_merge(merged, raw)
    return merged


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _deep_merge(target: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


def ensure_contact(state: Dict[str, Any], msisdn: str) -> Dict[str, Any]:
    contacts = state.setdefault("contacts", {})
    contact = contacts.setdefault(
        msisdn,
        {
            "name": "",
            "priority": "normal",  # low | normal | high | critical
            "last_seen_at": "",
            "last_intent": "",
            "last_messages": [],
            "tags": [],
            "stats": {"inbound": 0, "auto_replies": 0},
        },
    )
    return contact


def append_contact_message(state: Dict[str, Any], msisdn: str, text: str) -> None:
    contact = ensure_contact(state, msisdn)
    contact["last_seen_at"] = _now_iso()
    contact.setdefault("stats", {}).setdefault("inbound", 0)
    contact["stats"]["inbound"] += 1
    msgs = contact.setdefault("last_messages", [])
    msgs.append({"at": _now_iso(), "text": text})
    if len(msgs) > 10:
        del msgs[:-10]


def set_contact_intent(state: Dict[str, Any], msisdn: str, intent: str) -> None:
    contact = ensure_contact(state, msisdn)
    contact["last_intent"] = intent


def increment_auto_reply(state: Dict[str, Any], msisdn: str) -> None:
    contact = ensure_contact(state, msisdn)
    contact.setdefault("stats", {}).setdefault("auto_replies", 0)
    contact["stats"]["auto_replies"] += 1


def add_metric_event(state: Dict[str, Any], event: Dict[str, Any]) -> None:
    metrics = state.setdefault("metrics", {}).setdefault("events", [])
    payload = {"at": _now_iso(), **event}
    metrics.append(payload)
    if len(metrics) > 5000:
        del metrics[:-5000]
