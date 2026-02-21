"""Orquestador principal para mensajes de WhatsApp.

La idea es que el runtime de OpenClaw (o cualquier listener) haga:

    from clwabot.core.whatsapp_agent import handle_incoming

    decision = handle_incoming(msisdn, text)
    if decision["policy"] == "owner":
        # dejar que el agente responda libremente al owner
    elif decision["policy"] == "alert_owner":
        # enviar decision["message"] al owner
    elif decision["policy"] == "reply_to_vip":
        # enviar decision["message"] al VIP (catálogo, preguntas, etc.)
    else:
        # silencio

Por ahora implementamos:
- owner        → policy="owner"
- vip+urgente  → policy="alert_owner" (alerta básica)
- otros/otro   → policy="silence"

El flujo conversado 1–4 con el VIP se puede construir encima extendiendo
esta misma función (por ejemplo usando una pequeña máquina de estados
persistida en JSON).
"""

from typing import Dict, Literal

from .assistant_control import handle_owner_command, is_within_business_hours
from .auto_reply import pick_auto_reply
from .intent_router import classify_intent, classify_priority
from .validator import validate_message, OWNER_MSISDN, VIP_MSISDN
from .meeting_session import get_active_meeting_session, handle_meeting_message
from .state_store import (
  add_metric_event,
  append_contact_message,
  increment_auto_reply,
  load_state,
  save_state,
  set_contact_intent,
)
from .urgencia_session import get_active_session, handle_vip_urgency_message


Policy = Literal["owner", "alert_owner", "reply_to_vip", "silence"]


def handle_incoming(msisdn: str, text: str) -> Dict[str, str]:
  """Devuelve una decisión de alto nivel sobre qué hacer con el mensaje.

  Estructura del dict de respuesta:
  - policy:
      - "owner"        → el runtime deja que el agente responda normal al owner
      - "reply_to_vip" → hay que mandar message al VIP; owner_message opcional
      - "alert_owner"  → solo hay mensaje para el owner
      - "silence"      → no hacer nada
  - target_msisdn: destinatario principal de `message` (owner o vip)
  - message: texto principal a enviar (puede ir al owner o al vip según policy)
  - owner_message: texto adicional SOLO para el owner (puede ser "")
  """

  v = validate_message(msisdn, text)
  clean_text = text or ""
  state = load_state()

  intent = classify_intent(clean_text) if v.role != "owner" else "general"
  if v.role != "owner":
    priority = classify_priority(intent, clean_text)
    append_contact_message(state, msisdn, clean_text)
    set_contact_intent(state, msisdn, intent)
    state.setdefault("contacts", {}).setdefault(msisdn, {}).update({"priority": priority})
    add_metric_event(state, {"kind": "inbound", "msisdn": msisdn, "intent": intent, "priority": priority})
    save_state(state)

  # Mensajes del owner: se manejan en la capa del agente normal
  if v.role == "owner":
    cmd_resp = handle_owner_command(clean_text)
    if cmd_resp:
      return {
        "policy": "reply_to_vip",
        "target_msisdn": OWNER_MSISDN,
        "message": cmd_resp,
        "owner_message": "",
        "vip_ics_path": "",
        "owner_ics_path": "",
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
      }
    return {
      "policy": "owner",
      "target_msisdn": OWNER_MSISDN,
      "message": clean_text,
      "owner_message": "",
    }

  assistant_cfg = state.get("assistant", {})
  if assistant_cfg.get("paused", False):
    return {
      "policy": "silence",
      "target_msisdn": "",
      "message": "",
      "owner_message": "",
    }

  # VIP con urgencia o sesión activa → usar flujo 1–4 de sesiones
  if v.role == "vip" and (v.is_urgency or get_active_session(msisdn) is not None):
    sess_decision = handle_vip_urgency_message(msisdn, text or "")
    vip_msg = sess_decision.get("vip_message", "")
    owner_msg = sess_decision.get("owner_message", "")
    vip_ics_path = sess_decision.get("vip_ics_path", "")
    owner_ics_path = sess_decision.get("owner_ics_path", "")
    owner_retry_message = sess_decision.get("owner_retry_message", "")
    owner_retry_delay_sec = sess_decision.get("owner_retry_delay_sec", "0")

    if vip_msg or owner_msg or vip_ics_path or owner_ics_path or owner_retry_message:
      return {
        "policy": "reply_to_vip",
        "target_msisdn": VIP_MSISDN,
        "message": vip_msg,
        "owner_message": owner_msg,
        "vip_ics_path": vip_ics_path,
        "owner_ics_path": owner_ics_path,
        "owner_retry_message": owner_retry_message,
        "owner_retry_delay_sec": owner_retry_delay_sec,
      }

    # Sin acción específica
    return {
      "policy": "silence",
      "target_msisdn": "",
      "message": "",
      "owner_message": "",
      "vip_ics_path": "",
      "owner_ics_path": "",
      "owner_retry_message": "",
      "owner_retry_delay_sec": "0",
    }

  # Contactos externos: formulario de reunión con disparador por intención.
  if v.role == "other" and (get_active_meeting_session(msisdn) is not None or clean_text):
    if get_active_meeting_session(msisdn) is None and intent != "meeting" and not is_within_business_hours(state):
      mode = assistant_cfg.get("mode", "normal")
      off_msg = (
        "Hola, en este momento estoy fuera de horario. "
        "Si es urgente escribe URGENTE. Si es reunión, escribe 'agendar reunión' y te respondo apenas esté activo."
      )
      if mode == "vacation":
        off_msg = (
          "Hola, estoy en modo vacaciones. Puedo dejar tu mensaje registrado. "
          "Si necesitas reunión, escribe 'agendar reunión' y te contactaré en cuanto vuelva."
        )
      increment_auto_reply(state, msisdn)
      add_metric_event(state, {"kind": "auto_reply_off_hours", "msisdn": msisdn})
      save_state(state)
      return {
        "policy": "reply_to_vip",
        "target_msisdn": msisdn,
        "message": off_msg,
        "owner_message": "",
        "vip_ics_path": "",
        "owner_ics_path": "",
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
      }

    meeting = handle_meeting_message(msisdn, clean_text)
    contact_msg = meeting.get("contact_message", "")
    owner_msg = meeting.get("owner_message", "")
    contact_ics_path = meeting.get("contact_ics_path", "")
    owner_ics_path = meeting.get("owner_ics_path", "")
    followup_message = meeting.get("followup_message", "")
    followup_delay_sec = meeting.get("followup_delay_sec", "0")

    if contact_msg or owner_msg or contact_ics_path or owner_ics_path:
      increment_auto_reply(state, msisdn)
      add_metric_event(state, {"kind": "meeting_flow_reply", "msisdn": msisdn})
      save_state(state)
      return {
        "policy": "reply_to_vip",
        "target_msisdn": msisdn,
        "message": contact_msg,
        "owner_message": owner_msg,
        "vip_ics_path": contact_ics_path,
        "owner_ics_path": owner_ics_path,
        "followup_message": followup_message,
        "followup_delay_sec": followup_delay_sec,
        "owner_retry_message": "",
        "owner_retry_delay_sec": "0",
      }

    # Si no hay flujo de reunión activo, usar guion contextual por intención.
    if intent != "meeting":
      scripted = pick_auto_reply(intent)
      if scripted:
        increment_auto_reply(state, msisdn)
        add_metric_event(state, {"kind": "scripted_reply", "msisdn": msisdn, "intent": intent})
        save_state(state)
        return {
          "policy": "reply_to_vip",
          "target_msisdn": msisdn,
          "message": scripted,
          "owner_message": "",
          "vip_ics_path": "",
          "owner_ics_path": "",
          "followup_message": "",
          "followup_delay_sec": "0",
          "owner_retry_message": "",
          "owner_retry_delay_sec": "0",
        }

  # Cualquier otro caso: silencio total
  return {
    "policy": "silence",
    "target_msisdn": "",
    "message": "",
    "owner_message": "",
  }
