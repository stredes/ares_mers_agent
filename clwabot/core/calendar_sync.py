from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_PATH = BASE_DIR / "data" / "google_calendar_queue.json"


def queue_calendar_sync(payload: Dict[str, str]) -> None:
    """Encola eventos para sync externo (Google Calendar u otro worker)."""
    state = {"events": []}
    if QUEUE_PATH.exists():
        try:
            state = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {"events": []}

    state.setdefault("events", []).append(
        {"created_at": datetime.now(timezone.utc).isoformat(), "status": "pending", **payload}
    )
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
