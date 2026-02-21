#!/usr/bin/env python3
"""whatsapp_listener.py

Puente entre el gateway de OpenClaw y el proyecto clwabot.

Uso manual de prueba:

    python -m clwabot.hooks.whatsapp_listener \
        --msisdn +56975551112 \
        --text "urgencia, necesito ayuda con..."

El script:
- llama a clwabot.core.whatsapp_agent.handle_incoming
- según la decisión, usa `openclaw message send` para:
  - responder al VIP (catálogo, preguntas, cierre)
  - enviar alerta al owner (+56954764325)
"""

import argparse
import json
import shlex
import subprocess
import sys
import time
from hashlib import sha1
from pathlib import Path

OWNER_MSISDN = "+56954764325"
VIP_MSISDN = "+56975551112"
AUTO_RESPONSE_GRACE_SECONDS = 15
OWNER_CONNECTED_IDLE_SECONDS = 20
MAX_PENDING_EVENTS = 500

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

NODE_BIN = "/home/stredesmers/.nvm/versions/node/v24.13.1/bin/node"
OPENCLAW_MJS = "/home/stredesmers/.npm-global/lib/node_modules/openclaw/openclaw.mjs"

PRESENCE_PATH = BASE_DIR / "clwabot" / "data" / "owner_presence.json"
PENDING_PATH = BASE_DIR / "clwabot" / "data" / "pending_inbox.json"

from clwabot.core.meeting_session import get_active_meeting_session  # noqa: E402
from clwabot.core.intent_router import classify_intent  # noqa: E402
from clwabot.core.urgencia_session import get_active_session  # noqa: E402
from clwabot.core.validator import validate_message  # noqa: E402
from clwabot.core.whatsapp_agent import handle_incoming  # noqa: E402


def run_cmd(cmd: list[str]) -> int:
    """Ejecuta un comando y devuelve el exit code."""
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.stdout:
        print(proc.stdout, file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def openclaw_cmd(*args: str) -> list[str]:
    return [NODE_BIN, OPENCLAW_MJS, *args]


def send_whatsapp_text(target: str, message: str) -> None:
    """Envía un texto simple por WhatsApp usando openclaw CLI."""
    if not message.strip():
        return
    cmd = openclaw_cmd("message", "send", "--channel", "whatsapp", "--target", target, "--message", message)
    run_cmd(cmd)


def send_whatsapp_with_ics(target: str, message: str, ics_path: str) -> None:
    """Envía texto + archivo .ics como documento por WhatsApp."""
    if not message.strip():
        message = "Evento de calendario"
    cmd = openclaw_cmd(
        "message",
        "send",
        "--channel",
        "whatsapp",
        "--target",
        target,
        "--message",
        message,
        "--path",
        ics_path,
    )
    run_cmd(cmd)


def schedule_delayed_whatsapp_text(target: str, message: str, delay_sec: int) -> None:
    """Programa un envío diferido sin bloquear el proceso principal."""
    if not message.strip():
        return
    delay = max(1, min(int(delay_sec), 900))
    cmd = " ".join(
        shlex.quote(part)
        for part in openclaw_cmd("message", "send", "--channel", "whatsapp", "--target", target, "--message", message)
    )
    shell_cmd = f"sleep {delay}; {cmd}"
    subprocess.Popen(["bash", "-lc", shell_cmd])


def _load_presence() -> dict:
    if not PRESENCE_PATH.exists():
        return {"last_owner_activity_ts": 0}
    try:
        return json.loads(PRESENCE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"last_owner_activity_ts": 0}


def _save_presence(state: dict) -> None:
    PRESENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESENCE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_owner_activity() -> None:
    state = _load_presence()
    state["last_owner_activity_ts"] = int(time.time())
    _save_presence(state)


def owner_is_connected() -> bool:
    state = _load_presence()
    last = int(state.get("last_owner_activity_ts") or 0)
    if last <= 0:
        return False
    return (int(time.time()) - last) <= OWNER_CONNECTED_IDLE_SECONDS


def owner_activity_since(trigger_ts: int) -> bool:
    if trigger_ts <= 0:
        return False
    state = _load_presence()
    last = int(state.get("last_owner_activity_ts") or 0)
    return last >= trigger_ts


def _load_pending() -> dict:
    if not PENDING_PATH.exists():
        return {"events": []}
    try:
        return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"events": []}


def _save_pending(state: dict) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    events = state.get("events", [])
    if len(events) > MAX_PENDING_EVENTS:
        state["events"] = events[-MAX_PENDING_EVENTS:]
    PENDING_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _pending_id(msisdn: str, text: str, trigger_ts: int) -> str:
    raw = f"{msisdn}|{trigger_ts}|{text.strip()}"
    return sha1(raw.encode("utf-8")).hexdigest()


def add_pending_event(msisdn: str, text: str, trigger_ts: int) -> None:
    state = _load_pending()
    event_id = _pending_id(msisdn, text, trigger_ts)
    events = state.setdefault("events", [])
    for item in events:
        if item.get("id") == event_id:
            return
    events.append(
        {
            "id": event_id,
            "msisdn": msisdn,
            "text": text,
            "trigger_ts": int(trigger_ts),
            "status": "waiting_owner_check",
            "updated_ts": int(time.time()),
        }
    )
    _save_pending(state)


def resolve_pending_event(msisdn: str, text: str, trigger_ts: int, status: str) -> None:
    state = _load_pending()
    event_id = _pending_id(msisdn, text, trigger_ts)
    events = state.setdefault("events", [])
    for item in events:
        if item.get("id") == event_id:
            item["status"] = status
            item["updated_ts"] = int(time.time())
            break
    else:
        events.append(
            {
                "id": event_id,
                "msisdn": msisdn,
                "text": text,
                "trigger_ts": int(trigger_ts),
                "status": status,
                "updated_ts": int(time.time()),
            }
        )
    _save_pending(state)


def should_handle_as_pending(msisdn: str, text: str, role: str, is_urgency: bool) -> bool:
    if role == "owner":
        return False

    if role == "vip":
        return bool(is_urgency or get_active_session(msisdn) is not None)

    # Contactos externos: solo intents clave + sesiones activas.
    if get_active_meeting_session(msisdn) is not None:
        return True
    intent = classify_intent(text or "")
    return intent in {"meeting", "urgency", "support", "sales"}


def schedule_pending_gate(msisdn: str, text: str, trigger_ts: int) -> None:
    """Re-ejecuta listener luego de grace period para decidir si auto-responder."""
    cmd = (
        "python3 -m clwabot.hooks.whatsapp_listener "
        f"--msisdn {shlex.quote(msisdn)} "
        f"--text {shlex.quote(text)} "
        "--deferred-auto "
        f"--trigger-ts {int(trigger_ts)}"
    )
    shell_cmd = f"sleep {AUTO_RESPONSE_GRACE_SECONDS}; {cmd}"
    subprocess.Popen(["bash", "-lc", shell_cmd])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--msisdn", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--deferred-auto", action="store_true")
    parser.add_argument("--trigger-ts", type=int, default=0)
    args = parser.parse_args()

    msisdn = args.msisdn
    text = args.text
    is_deferred_auto = bool(args.deferred_auto)
    trigger_ts = int(args.trigger_ts or 0)

    validation = validate_message(msisdn, text)
    if validation.role == "owner":
        mark_owner_activity()

    # Mensajes de terceros se tratan como "pendientes": solo se responde
    # si pasan por keywords/tipo y no hubo actividad reciente del owner.
    pending_candidate = should_handle_as_pending(
        msisdn=msisdn,
        text=text,
        role=validation.role,
        is_urgency=validation.is_urgency,
    )
    if validation.role != "owner" and pending_candidate:
        if not is_deferred_auto:
            now_ts = int(time.time())
            add_pending_event(msisdn=msisdn, text=text, trigger_ts=now_ts)
            schedule_pending_gate(msisdn=msisdn, text=text, trigger_ts=now_ts)
            return 0
        if owner_activity_since(trigger_ts) or owner_is_connected():
            resolve_pending_event(msisdn=msisdn, text=text, trigger_ts=trigger_ts, status="seen_by_owner")
            return 0
        resolve_pending_event(msisdn=msisdn, text=text, trigger_ts=trigger_ts, status="processing")
    elif validation.role != "owner":
        return 0

    decision = handle_incoming(msisdn, text)

    policy = decision.get("policy")
    target_msisdn = decision.get("target_msisdn", "") or ""
    vip_msg = decision.get("message", "") or ""
    owner_msg = decision.get("owner_message", "") or ""
    vip_ics_path = decision.get("vip_ics_path", "") or ""
    owner_ics_path = decision.get("owner_ics_path", "") or ""
    owner_retry_msg = decision.get("owner_retry_message", "") or ""
    owner_retry_delay_raw = decision.get("owner_retry_delay_sec", "0") or "0"
    followup_msg = decision.get("followup_message", "") or ""
    followup_delay_raw = decision.get("followup_delay_sec", "0") or "0"
    try:
        owner_retry_delay = int(owner_retry_delay_raw)
    except ValueError:
        owner_retry_delay = 0
    try:
        followup_delay = int(followup_delay_raw)
    except ValueError:
        followup_delay = 0

    # 1) Mensajes del owner: los maneja el agente normal
    if policy == "owner":
        return 0

    # 2) Flujo VIP (catálogo/preguntas/cierre) + posible .ics
    if policy == "reply_to_vip":
        reply_target = target_msisdn or VIP_MSISDN
        if vip_msg:
            if vip_ics_path:
                send_whatsapp_with_ics(reply_target, vip_msg, vip_ics_path)
            else:
                send_whatsapp_text(reply_target, vip_msg)

        if owner_msg:
            if owner_ics_path and not vip_ics_path:
                send_whatsapp_with_ics(OWNER_MSISDN, owner_msg, owner_ics_path)
            else:
                send_whatsapp_text(OWNER_MSISDN, owner_msg)
        if owner_retry_msg and owner_retry_delay > 0:
            schedule_delayed_whatsapp_text(OWNER_MSISDN, owner_retry_msg, owner_retry_delay)
        if followup_msg and followup_delay > 0:
            schedule_delayed_whatsapp_text(reply_target, followup_msg, followup_delay)
        if validation.role != "owner" and trigger_ts > 0:
            resolve_pending_event(msisdn=msisdn, text=text, trigger_ts=trigger_ts, status="auto_replied")
        return 0

    # 3) Solo alerta al owner
    if policy == "alert_owner":
        if owner_msg:
            if owner_ics_path:
                send_whatsapp_with_ics(OWNER_MSISDN, owner_msg, owner_ics_path)
            else:
                send_whatsapp_text(OWNER_MSISDN, owner_msg)
        if validation.role != "owner" and trigger_ts > 0:
            resolve_pending_event(msisdn=msisdn, text=text, trigger_ts=trigger_ts, status="alerted_owner")
        return 0

    # 4) Silencio
    if validation.role != "owner" and trigger_ts > 0:
        resolve_pending_event(msisdn=msisdn, text=text, trigger_ts=trigger_ts, status="silenced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
