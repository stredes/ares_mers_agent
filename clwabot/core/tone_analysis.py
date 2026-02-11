#!/usr/bin/env python3
"""Análisis simple de tono para mensajes de WhatsApp.

No "siente" emociones, pero clasifica el texto en niveles según palabras
clave y patrones típicos. Pensado para ser usado cuando Lucas (stredes)
me pasa manualmente mensajes de su esposa u otras personas.

Niveles:
- 1: tranquilo / neutro
- 2: tensión / posible disgusto
- 3: conflicto / alta intensidad
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ToneLevel = Literal[1, 2, 3]


@dataclass
class ToneResult:
    level: ToneLevel
    reason: str


# Listas simples de palabras/frases clave. Se pueden ajustar con ejemplos reales.
SOFT_WORDS = [
    "amor",
    "bb",
    "cariño",
    "jaja",
    "jajaja",
    "jeje",
    "jiji",
    "mi vida",
]

NAME_PATTERNS = [
    "lucas",  # te llama por tu nombre → señal de seriedad
]

DISLIKE_PATTERNS = [
    "no me gusta",
    "no quiero que",
    "no quiero que hagas",
    "no quiero",
]

STRONG_PATTERNS = [
    "ya te dije",
    "ya te lo dije",
    "estoy cansada",
    "estoy cansado",
    "siempre haces",
    "nunca haces",
]

BAD_WORDS = [
    # no las escribo explícitas; puedes añadirse manualmente según tu realidad
]


def classify_tone(text: str) -> ToneResult:
    """Clasifica el tono general del mensaje.

    Heurística muy simple basada en presencia de palabras/expresiones.
    """

    t = text.lower().strip()

    # Por defecto: tranquilo
    level: ToneLevel = 1
    reasons: list[str] = []

    # Señales suaves
    if any(w in t for w in SOFT_WORDS):
        reasons.append("contiene palabras cariñosas / suaves")

    # Señales de tensión
    if any(p in t for p in NAME_PATTERNS):
        level = max(level, 2)
        reasons.append("te nombra como 'Lucas' → posible seriedad / tensión")

    if any(p in t for p in DISLIKE_PATTERNS):
        level = max(level, 2)
        reasons.append("expresa que algo no le gusta / no quiere")

    # Señales de conflicto
    if any(p in t for p in STRONG_PATTERNS):
        level = max(level, 3)
        reasons.append("frases fuertes tipo reproche ('ya te dije', 'estoy cansada', 'siempre/nunca')")

    if any(re.search(rf"\b{re.escape(w)}\b", t) for w in BAD_WORDS):
        level = max(level, 3)
        reasons.append("contiene palabras muy fuertes / insultos")

    if not reasons:
        reasons.append("sin señales fuertes detectadas; se asume tono tranquilo/neutro")

    return ToneResult(level=level, reason="; ".join(reasons))


if __name__ == "__main__":
    # Pruebas rápidas manuales
    samples = [
        "ya, amor, hablamos después jaja",
        "Lucas, no me gusta que hagas eso",
        "ya te dije que estoy cansada de esto",
    ]
    for s in samples:
        r = classify_tone(s)
        print(f"Texto: {s!r}\n → nivel={r.level}, motivo={r.reason}\n")
