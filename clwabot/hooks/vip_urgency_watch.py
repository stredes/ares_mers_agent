#!/usr/bin/env python3
"""
vip_urgency_watch.py

Lee líneas por stdin (por ejemplo, la salida de `openclaw logs --follow`)
y, cuando detecta un mensaje del VIP que contenga 'urgenc'
(urgente/urgencia), dispara el listener de clwabot para manejar
el protocolo 1-4.

Uso recomendado:

openclaw logs --follow | python3 -m clwabot.hooks.vip_urgency_watch
"""

import re
import shlex
import subprocess
import sys

from clwabot.core.urgencia_session import get_active_session

VIP_MSISDN = "+56975551112"
VIP_PATTERN = re.compile(r"\+?56975551112")
URGENC_PATTERN = re.compile(r"urgenc", re.IGNORECASE)


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


def extract_message(line: str) -> str:
    m = re.search(r'"([^"]+)"', line)
    if m:
        return m.group(1)
    return line.strip()


def main() -> int:
    print(
        "[vip_urgency_watch] escuchando stdin para VIP + trigger de urgencia/sesion activa",
        file=sys.stderr,
    )
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue

        if not VIP_PATTERN.search(line):
            continue

        session_active = get_active_session(VIP_MSISDN) is not None
        if not URGENC_PATTERN.search(line) and not session_active:
            continue

        msg = extract_message(line)
        print(
            f"[vip_urgency_watch] detectado mensaje VIP (urgencia/sesion): {msg}",
            file=sys.stderr,
        )
        run_listener(VIP_MSISDN, msg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
