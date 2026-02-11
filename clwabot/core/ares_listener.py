#!/usr/bin/env python3
"""Listener activo de logs de OpenClaw para ares_mers.

- Escucha el log diario de OpenClaw en /tmp/openclaw/openclaw-YYYY-MM-DD.log
- Detecta mensajes entrantes (inbound) de WhatsApp
- Espera unos segundos para permitir respuesta manual
- Si no hay respuesta, envía un mensaje automático
- Maneja trato especial para contacto VIP

Este script está pensado para ejecutarse como servicio de usuario (systemd --user).
"""

import os
import time
import subprocess
import re
from datetime import datetime

# === CONFIGURACIÓN TÁCTICA ===

# Ruta del log diario de OpenClaw (ajusta si cambia el patrón de logs)
LOG_DIR = "/tmp/openclaw"
LOG_FILE = os.path.join(LOG_DIR, f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log")

VIP_NUMBER = "+56975551112"
MY_NUMBER = "+56954764325"  # Número de stredes para no auto-responderte a ti

WAIT_TIME = 10  # segundos de espera antes de auto-responder

# Guion general de auto-respuesta (no VIP)
AUTO_REPLY_MSG = (
    "Hola, soy ares_mers, el asistente táctico de stredes.\n\n"
    "stredes está en una operación de alta prioridad y no puede responder ahora.\n"
    "- Si es una REUNIÓN: deja tema y hora.\n"
    "- Si es URGENTE: escribe 'URGENTE' y le daré prioridad.\n\n"
    "Try Harder."
)

# Mensaje especial para VIP (si decides usarlo distinto)
VIP_AUTO_REPLY_MSG = (
    "Hola, soy ares_mers. stredes está ocupado ahora mismo pero verá tu mensaje en cuanto pueda.\n\n"
    "Si es algo urgente, marca 'URGENTE' en el mensaje."
)


def send_whatsapp(target: str, message: str) -> None:
    """Envía un mensaje usando la CLI de OpenClaw.

    Se asume que el canal WhatsApp está configurado y que `openclaw message send`
    funciona desde el entorno donde se ejecute este script.
    """
    try:
        subprocess.run(
            [
                "openclaw",
                "message",
                "send",
                "--target",
                target,
                "--message",
                message,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[ares_listener] Error enviando mensaje a {target}: {e}")


def check_if_responded(target: str) -> bool:
    """Verifica en las últimas líneas del log si hubo respuesta hacia `target`.

    Busca patrones tipo "sent message to +56..." / "sending message to +56...".
    """
    if not os.path.exists(LOG_FILE):
        return False

    try:
        tail = subprocess.check_output(["tail", "-n", "40", LOG_FILE], text=True)
        tl = tail.lower()
        return (f"sent message to {target}" in tl) or (f"sending message to {target}" in tl)
    except Exception:  # noqa: BLE001
        return False


def ensure_log_file() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, "a").close()


def monitor_logs() -> None:
    ensure_log_file()
    print(f"[ares_listener] ares_mers activado. Monitoreando logs en {LOG_FILE}...")

    inbound_re = re.compile(r"from (\+\d+):", re.IGNORECASE)

    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        # Ir al final del archivo
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue

            lower = line.lower()

            # Detectar mensaje entrante (inbound) de WhatsApp
            if "[whatsapp]" in lower and "inbound" in lower:
                m = inbound_re.search(line)
                if not m:
                    continue

                sender = m.group(1)

                # Ignorar si eres tú mismo
                if sender == MY_NUMBER:
                    continue

                print(f"[ares_listener] Mensaje entrante detectado de {sender}. Esperando {WAIT_TIME}s...")
                time.sleep(WAIT_TIME)

                # Verificar si ya hubo respuesta manual
                if check_if_responded(sender):
                    print(f"[ares_listener] Ya hubo respuesta manual a {sender}. No envío auto-respuesta.")
                    continue

                # Elegir mensaje según si es VIP o no
                if sender == VIP_NUMBER:
                    msg = VIP_AUTO_REPLY_MSG
                    print(f"[ares_listener] Auto-respuesta VIP a {sender}.")
                else:
                    msg = AUTO_REPLY_MSG
                    print(f"[ares_listener] Auto-respuesta estándar a {sender}.")

                send_whatsapp(sender, msg)


if __name__ == "__main__":
    try:
        monitor_logs()
    except KeyboardInterrupt:
        print("[ares_listener] Detenido manualmente por stredes.")
