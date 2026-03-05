#!/usr/bin/env python3
"""
vip_urgency_watch.py

Lee líneas por stdin (por ejemplo, la salida de `openclaw logs --follow`)
y, cuando detecta un mensaje del VIP que contenga señales de urgencia
(urgente/urgencia/emergencia/etc), dispara el listener de clwabot para manejar
el protocolo 1-4.

Uso recomendado:

openclaw logs --follow | python3 -m clwabot.hooks.vip_urgency_watch
"""

from collections import deque
import re
import shlex
import subprocess
import sys
import time

from clwabot.core.urgencia_handler import mensaje_contiene_urgencia
from clwabot.core.urgencia_session import get_active_session
from clwabot.hooks.whatsapp_router_watch import parse_inbound_line

VIP_MSISDN = "+56975551112"
VIP_PATTERN = re.compile(r"\+?56975551112")
QUOTED_RE = re.compile(r'"([^"]+)"')
DEDUP_WINDOW_SECONDS = 4


def run_listener(msisdn: str, text: str) -> None:
    cmd = [
        "python3",
        "-m",
        "clwabot.hooks.whatsapp_listener",
        "--msisdn",
        msisdn,
        "--text",
        text,
    ]
    print(f"[vip_urgency_watch] disparando listener: {shlex.join(cmd)}", file=sys.stderr)
    subprocess.Popen(cmd)


def _normalize_msisdn(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _extract_message_from_text_line(line: str) -> str:
    m = QUOTED_RE.search(line)
    if m:
        return m.group(1)
    return line.strip()


def extract_vip_message(line: str) -> str | None:
    inbound = parse_inbound_line(line)
    if inbound is not None and _normalize_msisdn(inbound.msisdn) == _normalize_msisdn(VIP_MSISDN):
        return inbound.text.strip() or None

    # Fallback legacy: logs no estructurados que incluyan el número VIP.
    if VIP_PATTERN.search(line):
        msg = _extract_message_from_text_line(line)
        return msg or None
    return None


def should_dispatch(line: str, session_active: bool) -> str | None:
    msg = extract_vip_message(line)
    if not msg:
        return None

    # Puede venir truncado en logs: revisamos mensaje + línea completa.
    has_urgency = mensaje_contiene_urgencia(msg) or mensaje_contiene_urgencia(line)
    if not has_urgency and not session_active:
        return None
    return msg


def main() -> int:
    print(
        "[vip_urgency_watch] escuchando stdin para VIP + trigger de urgencia/sesion activa",
        file=sys.stderr,
    )
    recent = deque()

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue

        session_active = get_active_session(VIP_MSISDN) is not None
        msg = should_dispatch(line, session_active=session_active)
        if msg is None:
            continue

        now = time.time()
        while recent and (now - recent[0][1]) > DEDUP_WINDOW_SECONDS:
            recent.popleft()
        if any(sig == msg for sig, _ in recent):
            continue
        recent.append((msg, now))

        print(
            f"[vip_urgency_watch] detectado mensaje VIP (urgencia/sesion): {msg}",
            file=sys.stderr,
        )
        run_listener(VIP_MSISDN, msg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
