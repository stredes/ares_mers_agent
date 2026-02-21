"""Manejo de sesiones de urgencia VIP (flujo 1-4)."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from .ics_maker import TZ, make_ics
from .urgencia_handler import manejar_urgencia

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_PATH = BASE_DIR / "data" / "urgencia_sessions.json"


@dataclass
class UrgenciaSession:
    id: str
    msisdn: str
    state: str  # esperando_opcion | esperando_detalle | confirmando_detalle | esperando_event_config | cerrada
    kind: Optional[str] = None  # evento | nota | recordatorio | inmediata
    temp_detail: Optional[str] = None
    created_at: str = ""


ACTIVE_STATES = {
    "esperando_opcion",
    "esperando_detalle",
    "confirmando_detalle",
    "esperando_event_config",
}

CANCEL_WORDS = {"cancelar", "cancel", "salir", "anular"}
BACK_WORDS = {"volver", "atras", "atrás", "corregir", "editar"}
CONFIRM_WORDS = {"1", "si", "sí", "confirmar", "ok", "dale"}
EDIT_WORDS = {"2", "editar", "corregir", "cambiar"}
ABORT_WORDS = {"3", "cancelar", "anular", "salir"}

CATALOGO_TEXT = (
    "Hola amor, soy el asistente de Lucas. Veo que marcaste una urgencia.\n\n"
    "Para ayudarte mejor, responde con un número:\n"
    "1) Evento (calendario)\n"
    "2) Nota (que quede registrada para Lucas)\n"
    "3) Recordatorio con hora\n"
    "4) Urgencia inmediata (avisarle a Lucas ahora)\n\n"
    "Puedes responder 'cancelar' para salir del protocolo."
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_text(text: str) -> str:
    return " ".join(_strip_accents(text or "").strip().lower().split())


def _empty_response() -> Dict[str, str]:
    return {
        "vip_message": "",
        "owner_message": "",
        "vip_ics_path": "",
        "owner_ics_path": "",
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
    }


def _load_sessions() -> Dict[str, dict]:
    if not SESSIONS_PATH.exists():
        return {"sessions": []}
    try:
        return json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": []}


def _save_sessions(state: Dict[str, dict]) -> None:
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_session_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"urgsess-{now}"


def get_active_session(msisdn: str) -> Optional[UrgenciaSession]:
    state = _load_sessions()
    for raw in state.get("sessions", []):
        if raw.get("msisdn") == msisdn and raw.get("state") in ACTIVE_STATES:
            return UrgenciaSession(**raw)
    return None


def start_session(msisdn: str) -> UrgenciaSession:
    state = _load_sessions()
    sess = UrgenciaSession(
        id=_new_session_id(),
        msisdn=msisdn,
        state="esperando_opcion",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    state.setdefault("sessions", []).append(sess.__dict__)
    _save_sessions(state)
    return sess


def update_session(sess: UrgenciaSession) -> None:
    state = _load_sessions()
    sessions = state.setdefault("sessions", [])
    for idx, raw in enumerate(sessions):
        if raw.get("id") == sess.id:
            sessions[idx] = sess.__dict__
            break
    else:
        sessions.append(sess.__dict__)
    _save_sessions(state)


def _is_activation_text(text: str) -> bool:
    lowered = _normalize_text(text)
    return "urgente" in lowered or "urgencia" in lowered


def _parse_option(text: str) -> Optional[str]:
    clean = _normalize_text(text)
    if not clean:
        return None
    if clean[0] in {"1", "2", "3", "4"}:
        return clean[0]
    aliases = {
        "evento": "1",
        "nota": "2",
        "recordatorio": "3",
        "inmediata": "4",
        "urgencia inmediata": "4",
    }
    if clean in aliases:
        return aliases[clean]
    m = re.search(r"(?:opcion|opcion:|cambiar a|ir a)\s*([1-4])", clean)
    if m:
        return m.group(1)
    return None


def _is_explicit_option_switch(text: str) -> bool:
    clean = _normalize_text(text)
    return bool(re.search(r"(?:opcion|opcion:|cambiar a|ir a)\s*[1-4]", clean))


def prompt_for_kind(option: str) -> Optional[str]:
    opt = _parse_option(option) or ""
    if opt == "1":
        return (
            "Ok, evento. Escríbeme en un solo mensaje: título, fecha y hora.\n"
            "Ejemplo: Reunion banco, lunes 10:30\n"
            "Si quieres retroceder escribe 'volver'."
        )
    if opt == "2":
        return "Ok, nota. Escríbeme el texto que quieres que Lucas tenga presente."
    if opt == "3":
        return "Ok, recordatorio. Dime qué hay que recordar y para qué hora. Ej: pagar luz mañana 09:00"
    if opt == "4":
        return "Entendido, urgencia inmediata. Cuéntame en una frase qué pasó."
    return None


def kind_from_option(option: str) -> Optional[str]:
    mapping = {"1": "evento", "2": "nota", "3": "recordatorio", "4": "inmediata"}
    return mapping.get(_parse_option(option) or "")


def _parse_time(text: str) -> Optional[Tuple[int, int]]:
    clean = _normalize_text(text)
    if "mediodia" in clean:
        return (12, 0)
    if "medianoche" in clean:
        return (0, 0)

    m = re.search(r"\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(am|pm)?\b", clean)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2) or 0)
    ampm = m.group(3)
    if ampm == "pm" and hh < 12:
        hh += 12
    if ampm == "am" and hh == 12:
        hh = 0
    return (hh, mm)


def _next_weekday(base: datetime, weekday: int) -> datetime:
    delta = (weekday - base.weekday()) % 7
    return base + timedelta(days=delta)


def _parse_date(text: str, now: datetime) -> Optional[datetime]:
    clean = _normalize_text(text)
    if "pasado manana" in clean:
        return now + timedelta(days=2)
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
            return _next_weekday(now, idx)

    m_iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", clean)
    if m_iso:
        y, mo, d = map(int, m_iso.groups())
        try:
            return now.replace(year=y, month=mo, day=d)
        except ValueError:
            return None

    m_lat = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", clean)
    if m_lat:
        d = int(m_lat.group(1))
        mo = int(m_lat.group(2))
        y = int(m_lat.group(3) or now.year)
        try:
            return now.replace(year=y, month=mo, day=d)
        except ValueError:
            return None

    return None


def _parse_spanish_datetime(detail: str, default_plus_hours: int = 1) -> datetime:
    now = datetime.now(tz=TZ)
    date_base = _parse_date(detail, now) or now
    parsed_time = _parse_time(detail)
    if parsed_time is None:
        fallback = now + timedelta(hours=default_plus_hours)
        hh, mm = fallback.hour, fallback.minute
    else:
        hh, mm = parsed_time

    result = date_base.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if result <= now:
        result += timedelta(days=1)
    return result


def _extract_title_and_description(raw: str, fallback: str = "Evento") -> Tuple[str, str]:
    text = (raw or "").strip()
    if not text:
        return (fallback, "")
    if "," in text:
        title, rest = text.split(",", 1)
        return (title.strip() or fallback, rest.strip())
    if " - " in text:
        title, rest = text.split(" - ", 1)
        return (title.strip() or fallback, rest.strip())
    return (text[:80], text)


def _short_summary(text: str, max_len: int = 140) -> str:
    raw = " ".join((text or "").split())
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def _build_confirmation_message(kind: str, detail: str) -> str:
    return (
        "Perfecto, te resumo lo que registré:\n"
        f"- Tipo: {kind}\n"
        f"- Detalle: {_short_summary(detail, 220)}\n\n"
        "Responde:\n"
        "1) Confirmar\n"
        "2) Editar\n"
        "3) Cancelar"
    )


def _finalize_simple(kind: str, msisdn: str, detail: str) -> Dict[str, str]:
    owner_msg = manejar_urgencia(from_msisdn=msisdn, text=detail, kind=kind)
    resp = {
        "vip_message": "Gracias, ya quedó registrado y se lo envié a Lucas.",
        "owner_message": owner_msg,
        "vip_ics_path": "",
        "owner_ics_path": "",
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
    }
    if kind == "inmediata":
        resp["owner_retry_message"] = (
            "⚠️ REINTENTO AUTOMÁTICO: urgencia inmediata pendiente de atención.\n"
            f"Resumen: {_short_summary(detail)}"
        )
        resp["owner_retry_delay_sec"] = "120"
        resp["vip_message"] = "Ya lo marqué como URGENCIA INMEDIATA y lo estoy escalando a Lucas."
    return resp


def _finalize_recordatorio(msisdn: str, detail: str) -> Dict[str, str]:
    start = _parse_spanish_datetime(detail, default_plus_hours=1)
    title = "Recordatorio VIP"
    ics_path = make_ics(
        title=title,
        start=start,
        duration_minutes=30,
        description=detail,
    )
    full_text = f"[RECORDATORIO VIP] {detail} (ICS: {ics_path.name})"
    owner_msg = manejar_urgencia(from_msisdn=msisdn, text=full_text, kind="recordatorio")
    return {
        "vip_message": "Perfecto. Ya registré el recordatorio y lo envié con calendario.",
        "owner_message": owner_msg,
        "vip_ics_path": str(ics_path),
        "owner_ics_path": str(ics_path),
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
    }


def _finalize_event(msisdn: str, detail: str, all_day: bool) -> Dict[str, str]:
    title, description = _extract_title_and_description(detail, fallback="Evento VIP")
    start = _parse_spanish_datetime(detail, default_plus_hours=1)
    duration_minutes = 12 * 60 if all_day else 60
    prefix = "[EVENTO TODO EL DIA] " if all_day else "[EVENTO INICIO/FIN] "

    ics_path = make_ics(
        title=title,
        start=start,
        duration_minutes=duration_minutes,
        description=description or detail,
    )

    full_text = f"{prefix}{detail} (ICS: {ics_path.name})"
    owner_msg = manejar_urgencia(from_msisdn=msisdn, text=full_text, kind="evento")
    return {
        "vip_message": "Gracias, ya registré este evento para Lucas y generé un calendario.",
        "owner_message": owner_msg,
        "vip_ics_path": str(ics_path),
        "owner_ics_path": str(ics_path),
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
    }


def _handle_cancel(sess: UrgenciaSession) -> Dict[str, str]:
    sess.state = "cerrada"
    sess.temp_detail = None
    update_session(sess)
    return {
        "vip_message": "Perfecto, cerré este protocolo de urgencia. Si necesitas, escribe 'urgencia' para iniciar otro.",
        "owner_message": "",
        "vip_ics_path": "",
        "owner_ics_path": "",
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
    }


def _handle_back(sess: UrgenciaSession) -> Dict[str, str]:
    if sess.state == "esperando_detalle":
        sess.state = "esperando_opcion"
        sess.kind = None
    elif sess.state == "confirmando_detalle":
        sess.state = "esperando_detalle"
    elif sess.state == "esperando_event_config":
        sess.state = "esperando_detalle"
    sess.temp_detail = None
    update_session(sess)
    return {
        "vip_message": "Volvimos un paso atrás. Continúa desde aquí:\n" + CATALOGO_TEXT
        if sess.state == "esperando_opcion"
        else "Listo, reescribe el detalle para continuar.",
        "owner_message": "",
        "vip_ics_path": "",
        "owner_ics_path": "",
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
    }


def handle_vip_urgency_message(msisdn: str, text: str) -> Dict[str, str]:
    """Procesa un mensaje del VIP dentro del flujo de urgencia."""
    text = (text or "").strip()
    norm = _normalize_text(text)
    active = get_active_session(msisdn)

    if active is None:
        if not _is_activation_text(text):
            return _empty_response()
        start_session(msisdn)
        return {
            "vip_message": CATALOGO_TEXT,
            "owner_message": "",
            "vip_ics_path": "",
            "owner_ics_path": "",
            "owner_retry_message": "",
            "owner_retry_delay_sec": "0",
        }

    if norm in CANCEL_WORDS:
        return _handle_cancel(active)

    change_to = _parse_option(norm)
    if (
        change_to
        and _is_explicit_option_switch(norm)
        and active.state in {"esperando_detalle", "confirmando_detalle", "esperando_event_config"}
    ):
        active.kind = kind_from_option(change_to)
        active.state = "esperando_detalle"
        active.temp_detail = None
        update_session(active)
        return {
            "vip_message": f"Cambié a opción {change_to}. Ahora envíame el detalle.",
            "owner_message": "",
            "vip_ics_path": "",
            "owner_ics_path": "",
            "owner_retry_message": "",
            "owner_retry_delay_sec": "0",
        }

    if norm in BACK_WORDS:
        return _handle_back(active)

    if active.state == "esperando_opcion":
        k = kind_from_option(text)
        prompt = prompt_for_kind(text)
        if not k or not prompt:
            return {
                "vip_message": CATALOGO_TEXT,
                "owner_message": "",
                "vip_ics_path": "",
                "owner_ics_path": "",
                "owner_retry_message": "",
                "owner_retry_delay_sec": "0",
            }
        active.kind = k
        active.state = "esperando_detalle"
        update_session(active)
        return {
            "vip_message": prompt,
            "owner_message": "",
            "vip_ics_path": "",
            "owner_ics_path": "",
            "owner_retry_message": "",
            "owner_retry_delay_sec": "0",
        }

    if active.state == "esperando_detalle":
        if not text:
            return {
                "vip_message": "Necesito un poco más de detalle para continuar.",
                "owner_message": "",
                "vip_ics_path": "",
                "owner_ics_path": "",
                "owner_retry_message": "",
                "owner_retry_delay_sec": "0",
            }
        active.temp_detail = text
        active.state = "confirmando_detalle"
        update_session(active)
        return {
            "vip_message": _build_confirmation_message(active.kind or "generic", text),
            "owner_message": "",
            "vip_ics_path": "",
            "owner_ics_path": "",
            "owner_retry_message": "",
            "owner_retry_delay_sec": "0",
        }

    if active.state == "confirmando_detalle":
        if norm in EDIT_WORDS:
            active.state = "esperando_detalle"
            update_session(active)
            return {
                "vip_message": "Perfecto, envíame el detalle corregido.",
                "owner_message": "",
                "vip_ics_path": "",
                "owner_ics_path": "",
                "owner_retry_message": "",
                "owner_retry_delay_sec": "0",
            }
        if norm in ABORT_WORDS:
            return _handle_cancel(active)
        if norm not in CONFIRM_WORDS:
            return {
                "vip_message": _build_confirmation_message(active.kind or "generic", active.temp_detail or ""),
                "owner_message": "",
                "vip_ics_path": "",
                "owner_ics_path": "",
                "owner_retry_message": "",
                "owner_retry_delay_sec": "0",
            }

        detail = active.temp_detail or ""
        if active.kind == "evento":
            active.state = "esperando_event_config"
            update_session(active)
            return {
                "vip_message": (
                    "¿Cómo quieres configurar el evento?\n"
                    "1) Inicio y término (60 min)\n"
                    "2) Todo el día\n"
                    "Puedes escribir 'volver' para corregir detalle."
                ),
                "owner_message": "",
                "vip_ics_path": "",
                "owner_ics_path": "",
                "owner_retry_message": "",
                "owner_retry_delay_sec": "0",
            }

        if active.kind == "recordatorio":
            payload = _finalize_recordatorio(msisdn, detail)
        else:
            payload = _finalize_simple(active.kind or "generic", msisdn, detail)
        active.state = "cerrada"
        update_session(active)
        return payload

    if active.state == "esperando_event_config":
        if norm in {"2", "todo el dia", "todo el día"}:
            payload = _finalize_event(msisdn, active.temp_detail or "", all_day=True)
        elif norm in {"1", "inicio fin", "inicio y termino", "inicio y término"}:
            payload = _finalize_event(msisdn, active.temp_detail or "", all_day=False)
        else:
            return {
                "vip_message": "No entendí. Responde 1 para inicio/fin o 2 para todo el día.",
                "owner_message": "",
                "vip_ics_path": "",
                "owner_ics_path": "",
                "owner_retry_message": "",
                "owner_retry_delay_sec": "0",
            }
        active.state = "cerrada"
        update_session(active)
        return payload

    active.state = "cerrada"
    update_session(active)
    return _empty_response()
