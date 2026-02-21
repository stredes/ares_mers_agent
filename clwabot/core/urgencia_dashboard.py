from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
URGENCIAS_PATH = BASE_DIR / "data" / "urgencias.json"
SESSIONS_PATH = BASE_DIR / "data" / "urgencia_sessions.json"


def _load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_dashboard(hours: int = 24) -> str:
    urgencias_data = _load_json(URGENCIAS_PATH, {"urgencias": []})
    sessions_data = _load_json(SESSIONS_PATH, {"sessions": []})

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max(1, hours))

    urgencias = urgencias_data.get("urgencias", [])
    recent = []
    for u in urgencias:
        created = _parse_iso(u.get("created_at", ""))
        if created is None:
            continue
        if created >= cutoff:
            recent.append(u)

    active_sessions = [
        s
        for s in sessions_data.get("sessions", [])
        if s.get("state") in {"esperando_opcion", "esperando_detalle", "confirmando_detalle", "esperando_event_config"}
    ]

    by_kind = Counter(u.get("kind", "generic") for u in recent)
    critical = [u for u in recent if u.get("severity") == "critical"]
    duplicates = [u for u in recent if u.get("is_duplicate")]

    lines = []
    lines.append("[DASHBOARD URGENCIAS - clwabot]")
    lines.append(f"Ventana: ultimas {hours}h (UTC)")
    lines.append(f"Generado: {now.isoformat()}")
    lines.append("")
    lines.append("--- RESUMEN ---")
    lines.append(f"Total urgencias (ventana): {len(recent)}")
    lines.append(f"Criticas: {len(critical)}")
    lines.append(f"Duplicadas detectadas: {len(duplicates)}")
    lines.append(f"Sesiones activas: {len(active_sessions)}")
    lines.append("")
    lines.append("--- POR TIPO ---")
    if by_kind:
        for kind, count in by_kind.most_common():
            lines.append(f"- {kind}: {count}")
    else:
        lines.append("- (sin urgencias en ventana)")
    lines.append("")
    lines.append("--- SESIONES ACTIVAS ---")
    if active_sessions:
        for s in active_sessions:
            lines.append(
                f"- {s.get('msisdn')} | state={s.get('state')} | kind={s.get('kind') or '-'} | id={s.get('id')}"
            )
    else:
        lines.append("- (ninguna)")
    lines.append("")
    lines.append("--- ULTIMAS 5 ---")
    for u in sorted(recent, key=lambda item: item.get("created_at", ""), reverse=True)[:5]:
        lines.append(
            f"- {u.get('created_at')} | {u.get('kind')} | {u.get('severity', 'normal')} | {_compact(u.get('text', ''))}"
        )
    if not recent:
        lines.append("- (sin registros)")

    return "\n".join(lines)


def _compact(text: str, max_len: int = 100) -> str:
    value = " ".join((text or "").split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard de urgencias clwabot")
    parser.add_argument("--hours", type=int, default=24, help="Ventana en horas (default: 24)")
    args = parser.parse_args()
    print(build_dashboard(hours=args.hours))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
