#!/usr/bin/env python3
"""Helper para enviar media por WhatsApp usando la CLI de OpenClaw.

Uso pensado:
  python3 clwabot/core/send_media.py +569XXXXXXXX /ruta/al/archivo "Caption opcional"

Este script asume que:
- `openclaw message send --channel whatsapp --target ... --path ...` está configurado
  correctamente en tu entorno.
"""

import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Uso: send_media.py <numero_destino> <ruta_archivo> [caption]")
        return 1

    target = argv[1]
    path = Path(argv[2]).expanduser().resolve()
    caption = argv[3] if len(argv) > 3 else ""

    if not path.exists():
        print(f"[send_media] El archivo no existe: {path}")
        return 1

    cmd = [
        "openclaw",
        "message",
        "send",
        "--channel",
        "whatsapp",
        "--target",
        target,
        "--path",
        str(path),
    ]

    if caption:
        cmd.extend(["--caption", caption])

    print(f"[send_media] Ejecutando: {' '.join(cmd)}")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if proc.stdout:
            print(proc.stdout.strip())
        if proc.stderr:
            print(proc.stderr.strip())
        return 0
    except subprocess.CalledProcessError as e:
        print("[send_media] Error al enviar media:")
        print(e.stdout)
        print(e.stderr)
        return e.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
