from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .state_store import load_state, save_state

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _events_since(hours: int) -> list[dict]:
    state = load_state()
    events = state.get("metrics", {}).get("events", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for ev in events:
        try:
            at = datetime.fromisoformat(ev.get("at", ""))
        except Exception:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at >= cutoff:
            out.append(ev)
    return out


def _write_report(filename_prefix: str, text: str) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = REPORTS_DIR / f"{filename_prefix}_{ts}.txt"
    out.write_text(text, encoding="utf-8")
    return out


def generate_daily_report() -> Path:
    events = _events_since(24)
    by_kind = Counter(ev.get("kind", "unknown") for ev in events)
    by_contact = Counter(ev.get("msisdn", "n/a") for ev in events if ev.get("msisdn"))
    top_contact = by_contact.most_common(1)[0][0] if by_contact else "N/A"

    text = (
        "[REPORTE TACTICO DIARIO - ares_mers]\n"
        f"Fecha: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"Eventos 24h: {len(events)}\n"
        f"Top contacto: {top_contact}\n"
        "--- EVENTOS POR TIPO ---\n"
    )
    for kind, count in by_kind.most_common():
        text += f"- {kind}: {count}\n"

    out = _write_report("daily_report", text)
    state = load_state()
    state.setdefault("reports", {})["last_daily_report"] = datetime.now().strftime("%Y-%m-%d")
    save_state(state)
    return out


def generate_weekly_report() -> Path:
    events = _events_since(24 * 7)
    by_kind = Counter(ev.get("kind", "unknown") for ev in events)
    by_intent = Counter(ev.get("intent", "unknown") for ev in events if ev.get("intent"))
    urgencies = sum(1 for ev in events if ev.get("kind") in {"meeting_flow_reply", "auto_reply_off_hours"} or ev.get("intent") == "urgency")

    text = (
        "[REPORTE SEMANAL - ares_mers]\n"
        f"Semana ending: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"Eventos 7d: {len(events)}\n"
        f"Urgencias detectadas: {urgencies}\n"
        "--- POR KIND ---\n"
    )
    for kind, count in by_kind.most_common():
        text += f"- {kind}: {count}\n"

    text += "--- INTENCIONES ---\n"
    for intent, count in by_intent.most_common():
        text += f"- {intent}: {count}\n"

    out = _write_report("weekly_report", text)
    state = load_state()
    state.setdefault("reports", {})["last_weekly_report"] = datetime.now().strftime("%Y-%m-%d")
    save_state(state)
    return out


if __name__ == "__main__":
    path = generate_daily_report()
    print(str(path))
