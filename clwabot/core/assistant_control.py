from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import pytz

from .meeting_session import get_active_meeting_session, handle_meeting_message
from .oscp_agent import (
    add_lab_note,
    format_labs_text,
    format_plan_text,
    format_status_text,
    get_next_action,
    set_lab_status,
)
from .state_store import load_state, save_state
from .urgencia_session import get_active_session


def _parse_hhmm(value: str) -> tuple[int, int]:
    hh, mm = value.split(":")
    return int(hh), int(mm)


def is_within_business_hours(state: dict) -> bool:
    cfg = state.get("assistant", {}).get("business_hours", {})
    tz_name = cfg.get("timezone", "America/Santiago")
    start = cfg.get("start", "09:00")
    end = cfg.get("end", "19:00")

    tz = pytz.timezone(tz_name)
    now = datetime.now(tz=tz)
    sh, sm = _parse_hhmm(start)
    eh, em = _parse_hhmm(end)
    current = now.hour * 60 + now.minute
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    return start_min <= current <= end_min


def owner_status_text() -> str:
    state = load_state()
    assistant = state.get("assistant", {})
    contacts = state.get("contacts", {})
    active_urg = sum(1 for msisdn in contacts if get_active_session(msisdn) is not None)
    active_meet = sum(1 for msisdn in contacts if get_active_meeting_session(msisdn) is not None)
    return (
        "Estado asistente\n"
        f"- paused: {assistant.get('paused', False)}\n"
        f"- mode: {assistant.get('mode', 'normal')}\n"
        f"- business_hours: {assistant.get('business_hours', {}).get('start', '09:00')}-"
        f"{assistant.get('business_hours', {}).get('end', '19:00')}\n"
        f"- contactos en memoria: {len(contacts)}\n"
        f"- sesiones urgencia activas: {active_urg}\n"
        f"- sesiones reunión activas: {active_meet}"
    )


def handle_owner_command(text: str) -> Optional[str]:
    cmd = (text or "").strip()
    if not cmd.startswith("/"):
        return None

    state = load_state()
    assistant = state.setdefault("assistant", {})
    parts = cmd.split()
    op = parts[0].lower()

    if op in {"/status", "/agente", "/agente-status"}:
        return owner_status_text()

    if op in {"/pausar", "/agente-off"}:
        assistant["paused"] = True
        save_state(state)
        return "Asistente pausado."

    if op in {"/reanudar", "/agente-on"}:
        assistant["paused"] = False
        save_state(state)
        return "Asistente reanudado."

    if op in {"/modo"} and len(parts) >= 2:
        mode = parts[1].lower()
        if mode not in {"normal", "busy", "vacation"}:
            return "Modo inválido. Usa: /modo normal|busy|vacation"
        assistant["mode"] = mode
        save_state(state)
        return f"Modo actualizado: {mode}"

    if op in {"/forzar-reunion"} and len(parts) >= 2:
        target = parts[1]
        payload = handle_meeting_message(target, "quiero agendar una reunion")
        return payload.get("contact_message", "No se pudo iniciar formulario de reunión.")

    if op in {"/oscp-status"}:
        return format_status_text()

    if op in {"/oscp-plan"}:
        return format_plan_text()

    if op in {"/oscp-next"}:
        return get_next_action()

    if op in {"/oscp-labs"}:
        return format_labs_text()

    if op in {"/oscp-lab"} and len(parts) >= 3:
        status_map = {
            "pending": "pending",
            "pendiente": "pending",
            "in_progress": "in_progress",
            "en_curso": "in_progress",
            "curso": "in_progress",
            "rooted": "rooted",
            "completo": "rooted",
        }
        status = status_map.get(parts[-1].lower())
        if not status:
            return "Estado inválido. Usa: pending | in_progress | rooted"
        lab_name = " ".join(parts[1:-1]).strip()
        if not lab_name:
            return "Uso: /oscp-lab <nombre> <pending|in_progress|rooted>"
        return set_lab_status(lab_name, status)

    if op in {"/oscp-note"} and len(parts) >= 3:
        payload = cmd[len(parts[0]) :].strip()
        if "|" not in payload:
            return "Uso: /oscp-note <lab> | <nota>"
        lab_name, note = payload.split("|", 1)
        if not lab_name.strip() or not note.strip():
            return "Uso: /oscp-note <lab> | <nota>"
        return add_lab_note(lab_name.strip(), note.strip())

    if op in {"/horario"} and len(parts) >= 3:
        start = parts[1]
        end = parts[2]
        assistant.setdefault("business_hours", {})["start"] = start
        assistant.setdefault("business_hours", {})["end"] = end
        save_state(state)
        return f"Horario actualizado: {start}-{end}"

    if op in {"/ayuda"}:
        return (
            "Comandos:\n"
            "/status\n"
            "/pausar | /reanudar\n"
            "/modo normal|busy|vacation\n"
            "/horario HH:MM HH:MM\n"
            "/forzar-reunion +MSISDN\n"
            "/oscp-status | /oscp-plan | /oscp-next | /oscp-labs\n"
            "/oscp-lab <nombre> <pending|in_progress|rooted>\n"
            "/oscp-note <lab> | <nota>"
        )

    return "Comando no reconocido. Usa /ayuda"
