#!/usr/bin/env python3
"""Router general de inbound WhatsApp -> clwabot listener.

Uso recomendado:
  openclaw logs --follow | python3 -m clwabot.hooks.whatsapp_router_watch
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

INBOUND_TAG = "[whatsapp]"
FROM_RE = re.compile(r"from\s+(\+?\d{8,15})", re.IGNORECASE)
ANY_PHONE_RE = re.compile(r"(\+?\d{8,15})")
QUOTED_RE = re.compile(r'"([^"]+)"')
DEDUP_WINDOW_SECONDS = 4


@dataclass
class InboundMessage:
    msisdn: str
    text: str


def parse_inbound_line(line: str) -> Optional[InboundMessage]:
    lower = line.lower()
    if INBOUND_TAG not in lower or "inbound" not in lower:
        return None

    m_from = FROM_RE.search(line)
    if m_from:
        msisdn = m_from.group(1)
    else:
        m_phone = ANY_PHONE_RE.search(line)
        if not m_phone:
            return None
        msisdn = m_phone.group(1)

    quoted = QUOTED_RE.findall(line)
    if quoted:
        text = quoted[-1].strip()
    else:
        if ":" in line:
            text = line.split(":", 1)[1].strip()
        else:
            text = line.strip()

    if not text:
        return None

    return InboundMessage(msisdn=msisdn, text=text)


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
    print(f"[whatsapp_router_watch] dispatch: {shlex.join(cmd)}", file=sys.stderr)
    subprocess.Popen(cmd)


def main() -> int:
    print("[whatsapp_router_watch] listening stdin for WhatsApp inbound...", file=sys.stderr)
    recent = deque()

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue

        inbound = parse_inbound_line(line)
        if inbound is None:
            continue

        now = time.time()
        while recent and (now - recent[0][1]) > DEDUP_WINDOW_SECONDS:
            recent.popleft()

        signature = (inbound.msisdn, inbound.text)
        if any(sig == signature for sig, _ in recent):
            continue

        recent.append((signature, now))
        run_listener(inbound.msisdn, inbound.text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
