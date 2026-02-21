from __future__ import annotations

import unicodedata
from typing import Literal

Intent = Literal["meeting", "urgency", "support", "sales", "personal", "general"]
Priority = Literal["low", "normal", "high", "critical"]


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text or "")
    clean = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return " ".join(clean.lower().split())


def classify_intent(text: str) -> Intent:
    t = _normalize(text)
    if any(k in t for k in ("urgente", "urgencia", "emergencia", "critico", "crítico")):
        return "urgency"
    if any(k in t for k in ("reunion", "meeting", "agendar", "agenda", "llamada", "cita", "calendario")):
        return "meeting"
    if any(k in t for k in ("error", "bug", "falla", "no funciona", "problema", "soporte")):
        return "support"
    if any(k in t for k in ("precio", "cotizacion", "cotización", "demo", "propuesta", "venta", "comprar")):
        return "sales"
    if any(k in t for k in ("familia", "personal", "amigo", "hola lucas")):
        return "personal"
    return "general"


def classify_priority(intent: Intent, text: str) -> Priority:
    t = _normalize(text)
    if intent == "urgency":
        return "critical"
    if intent in {"meeting", "sales", "support"}:
        if any(k in t for k in ("hoy", "ahora", "asap", "urgente", "inmediato")):
            return "high"
        return "normal"
    if intent == "personal":
        return "normal"
    return "low"
