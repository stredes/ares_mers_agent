from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import yaml

from .calendar_sync import queue_calendar_sync
from .ics_maker import TZ, make_ics

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_PATH = BASE_DIR / "data" / "meeting_sessions.json"
SCRIPTS_PATH = BASE_DIR / "config" / "scripts.yaml"

TRIGGER_WORDS = {
    "reunion",
    "reunión",
    "agendar",
    "agenda",
    "meeting",
    "llamada",
    "cita",
    "calendario",
    "juntarnos",
}

ACTIVE_STATES = {"awaiting_topic", "awaiting_date", "awaiting_time", "awaiting_duration", "awaiting_mode", "confirming"}

CANCEL_WORDS = {"cancelar", "salir", "anular"}
CONFIRM_WORDS = {"1", "si", "sí", "confirmar", "ok", "dale"}
EDIT_WORDS = {"2", "editar", "corregir"}


@dataclass
class MeetingSession:
    id: str
    msisdn: str
    state: str
    topic: str = ""
    date_text: str = ""
    time_text: str = ""
    duration_text: str = ""
    mode_text: str = ""
    created_at: str = ""


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize(text: str) -> str:
    return " ".join(_strip_accents(text).lower().split())


def _load_scripts() -> dict:
    if not SCRIPTS_PATH.exists():
        return {}
    try:
        return yaml.safe_load(SCRIPTS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _load_sessions() -> Dict[str, list]:
    if not SESSIONS_PATH.exists():
        return {"sessions": []}
    try:
        return json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": []}


def _save_sessions(state: Dict[str, list]) -> None:
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_session_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"meet-{now}"


def get_active_meeting_session(msisdn: str) -> Optional[MeetingSession]:
    state = _load_sessions()
    for raw in state.get("sessions", []):
        if raw.get("msisdn") == msisdn and raw.get("state") in ACTIVE_STATES:
            return MeetingSession(**raw)
    return None


def _start_session(msisdn: str) -> MeetingSession:
    state = _load_sessions()
    sess = MeetingSession(
        id=_new_session_id(),
        msisdn=msisdn,
        state="awaiting_topic",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    state.setdefault("sessions", []).append(sess.__dict__)
    _save_sessions(state)
    return sess


def _update_session(sess: MeetingSession) -> None:
    state = _load_sessions()
    sessions = state.setdefault("sessions", [])
    for idx, raw in enumerate(sessions):
        if raw.get("id") == sess.id:
            sessions[idx] = sess.__dict__
            break
    else:
        sessions.append(sess.__dict__)
    _save_sessions(state)


def has_meeting_trigger(text: str) -> bool:
    normalized = _normalize(text)
    return any(word in normalized for word in TRIGGER_WORDS)


def _intro_message() -> str:
    scripts = _load_scripts()
    identity = scripts.get("identity", {})
    scripts_block = scripts.get("scripts", {})
    agent_name = identity.get("agent_name", "asistente")
    user_name = identity.get("user_name", "Lucas")
    meeting_script = scripts_block.get("meeting_request", "").strip()

    base = (
        f"Hola 👋 Soy {agent_name}, asistente de {user_name}.\n"
        "Te ayudo a agendar una reunión en formato rápido.\n\n"
        "Ejemplo de respuesta para tema:\n"
        "Revisión de propuesta comercial\n\n"
        "Primero: ¿cuál es el tema de la reunión?"
    )
    if meeting_script:
        return f"{base}\n\nReferencia:\n{meeting_script}"
    return base


def _parse_duration_minutes(text: str) -> int:
    clean = _normalize(text)
    if "30" in clean:
        return 30
    if "90" in clean:
        return 90
    if "1 hora" in clean or "1h" in clean or "60" in clean:
        return 60
    m = re.search(r"\b(\d{2,3})\b", clean)
    if m:
        val = int(m.group(1))
        if 15 <= val <= 240:
            return val
    return 60


def _parse_date(text: str, now: datetime) -> datetime:
    clean = _normalize(text)
    if "manana" in clean:
        return now + timedelta(days=1)
    if "hoy" in clean:
        return now

    weekdays = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "domingo": 6,
    }
    for name, idx in weekdays.items():
        if name in clean:
            delta = (idx - now.weekday()) % 7
            return now + timedelta(days=delta)

    m_lat = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", clean)
    if m_lat:
        day = int(m_lat.group(1))
        month = int(m_lat.group(2))
        year = int(m_lat.group(3) or now.year)
        try:
            return now.replace(year=year, month=month, day=day)
        except ValueError:
            return now
    return now


def _parse_time(text: str, now: datetime) -> tuple[int, int]:
    clean = _normalize(text)
    m = re.search(r"\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(am|pm)?\b", clean)
    if not m:
        return (now.hour + 1) % 24, now.minute
    hh = int(m.group(1))
    mm = int(m.group(2) or 0)
    ampm = m.group(3)
    if ampm == "pm" and hh < 12:
        hh += 12
    if ampm == "am" and hh == 12:
        hh = 0
    return hh, mm


def _build_start_datetime(date_text: str, time_text: str) -> datetime:
    now = datetime.now(tz=TZ)
    date_base = _parse_date(date_text, now)
    hh, mm = _parse_time(time_text, now)
    start = date_base.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if start <= now:
        start += timedelta(days=1)
    return start


def _summary(sess: MeetingSession) -> str:
    return (
        "Perfecto, este es el borrador de la reunión:\n"
        f"- Tema: {sess.topic}\n"
        f"- Fecha: {sess.date_text}\n"
        f"- Hora: {sess.time_text}\n"
        f"- Duración: {sess.duration_text}\n"
        f"- Modalidad: {sess.mode_text}\n\n"
        "Responde:\n"
        "1) Confirmar y agendar\n"
        "2) Editar datos\n"
        "o escribe 'cancelar'."
    )


def _finalize_ics(sess: MeetingSession) -> Dict[str, str]:
    start = _build_start_datetime(sess.date_text, sess.time_text)
    duration_minutes = _parse_duration_minutes(sess.duration_text)
    title = f"Reunión: {sess.topic}"[:120]
    description = (
        f"Solicitante: {sess.msisdn}\n"
        f"Modalidad: {sess.mode_text}\n"
        f"Duración declarada: {sess.duration_text}\n"
    )
    ics_path = make_ics(
        title=title,
        start=start,
        duration_minutes=duration_minutes,
        description=description,
        location=sess.mode_text[:120],
    )
    owner_msg = (
        "📅 Nueva solicitud de reunión\n"
        f"Contacto: {sess.msisdn}\n"
        f"Tema: {sess.topic}\n"
        f"Fecha/hora: {sess.date_text} {sess.time_text}\n"
        f"Duración: {sess.duration_text}\n"
        f"Modalidad: {sess.mode_text}\n"
        f"ICS: {ics_path.name}"
    )
    queue_calendar_sync(
        {
            "source": "meeting_session",
            "msisdn": sess.msisdn,
            "title": title,
            "start_iso": start.isoformat(),
            "duration_minutes": str(duration_minutes),
            "location": sess.mode_text[:120],
            "description": description,
            "ics_path": str(ics_path),
        }
    )
    return {
        "contact_message": "Listo, reunión agendada. Te envié un archivo de calendario (.ics).",
        "owner_message": owner_msg,
        "contact_ics_path": str(ics_path),
        "owner_ics_path": str(ics_path),
        "followup_message": "Hola, confirmo que tu reunión sigue agendada. Si quieres cambios, responde a este chat.",
        "followup_delay_sec": str(24 * 60 * 60),
    }


def _cancel_session(sess: MeetingSession) -> Dict[str, str]:
    sess.state = "closed"
    _update_session(sess)
    return {
        "contact_message": "Proceso cancelado. Si quieres reintentar, escribe 'agendar reunión'.",
        "owner_message": "",
        "contact_ics_path": "",
        "owner_ics_path": "",
        "followup_message": "",
        "followup_delay_sec": "0",
    }


def handle_meeting_message(msisdn: str, text: str) -> Dict[str, str]:
    """Gestiona formulario de agendamiento para contactos externos."""
    text = (text or "").strip()
    norm = _normalize(text)
    sess = get_active_meeting_session(msisdn)

    if sess is None:
        if not has_meeting_trigger(text):
            return {
                "contact_message": "",
                "owner_message": "",
                "contact_ics_path": "",
                "owner_ics_path": "",
                "followup_message": "",
                "followup_delay_sec": "0",
            }
        _start_session(msisdn)
        return {
            "contact_message": _intro_message(),
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    if norm in CANCEL_WORDS:
        return _cancel_session(sess)

    if sess.state == "awaiting_topic":
        sess.topic = text
        sess.state = "awaiting_date"
        _update_session(sess)
        return {
            "contact_message": "Perfecto. ¿Qué fecha te acomoda? (ej: mañana, lunes, 20/03)",
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    if sess.state == "awaiting_date":
        sess.date_text = text
        sess.state = "awaiting_time"
        _update_session(sess)
        return {
            "contact_message": "Genial. ¿A qué hora? (ej: 10:30 o 3pm)",
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    if sess.state == "awaiting_time":
        sess.time_text = text
        sess.state = "awaiting_duration"
        _update_session(sess)
        return {
            "contact_message": "¿Cuánto debería durar? (ej: 30 min, 1 hora)",
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    if sess.state == "awaiting_duration":
        sess.duration_text = text
        sess.state = "awaiting_mode"
        _update_session(sess)
        return {
            "contact_message": "Último dato: ¿modalidad? (videollamada, llamada o presencial)",
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    if sess.state == "awaiting_mode":
        sess.mode_text = text
        sess.state = "confirming"
        _update_session(sess)
        return {
            "contact_message": _summary(sess),
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    if sess.state == "confirming":
        if norm in CONFIRM_WORDS:
            payload = _finalize_ics(sess)
            sess.state = "closed"
            _update_session(sess)
            return payload
        if norm in EDIT_WORDS:
            sess.state = "awaiting_topic"
            _update_session(sess)
            return {
                "contact_message": "Ok, reingresemos los datos. ¿Cuál es el tema de la reunión?",
                "owner_message": "",
                "contact_ics_path": "",
                "owner_ics_path": "",
                "followup_message": "",
                "followup_delay_sec": "0",
            }
        return {
            "contact_message": _summary(sess),
            "owner_message": "",
            "contact_ics_path": "",
            "owner_ics_path": "",
            "followup_message": "",
            "followup_delay_sec": "0",
        }

    sess.state = "closed"
    _update_session(sess)
    return {
        "contact_message": "",
        "owner_message": "",
        "contact_ics_path": "",
        "owner_ics_path": "",
        "followup_message": "",
        "followup_delay_sec": "0",
    }
