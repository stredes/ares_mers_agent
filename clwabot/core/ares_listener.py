#!/usr/bin/env python3
"""Wrapper de compatibilidad para arrancar el router de WhatsApp.

Este módulo reemplaza el listener legacy basado en auto-reply fijo.
Ahora delega a:
  openclaw logs --follow | python3 -m clwabot.hooks.whatsapp_router_watch
"""

import shlex
import subprocess


def main() -> int:
    cmd = "openclaw logs --follow | python3 -m clwabot.hooks.whatsapp_router_watch"
    print(f"[ares_listener] starting unified router: {cmd}")
    return subprocess.call(["bash", "-lc", cmd])


if __name__ == "__main__":
    raise SystemExit(main())
