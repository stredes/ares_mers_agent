#!/usr/bin/env python3
"""Check-in periódico para VIP (+56975551112).

Envía un mensaje cariñoso usando la CLI de OpenClaw.
Pensado para usarse 2 veces al día (mañana y tarde) vía cron/cron de OpenClaw.
"""

import subprocess

TARGET = "+56975551112"
MESSAGE = (
    "Hola mi amor, soy el asistente de Lucas 💖, "
    "solo paso a preguntarte cómo estás y desearte un buen día."
)


def send_checkin() -> None:
    try:
        subprocess.run(
            [
                "openclaw",
                "message",
                "send",
                "--target",
                TARGET,
                "--message",
                MESSAGE,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[vip_checkin] Error enviando mensaje a {TARGET}: {e}")


if __name__ == "__main__":
    send_checkin()
