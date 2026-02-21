import json
import uuid
from difflib import SequenceMatcher
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "urgencias.json"
CALENDAR_DIR = BASE_DIR / "calendar"
DEDUP_WINDOW_SECONDS = 120
SEMANTIC_SIMILARITY_THRESHOLD = 0.88

CALENDAR_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Urgencia:
  id: str
  from_msisdn: str
  text: str
  created_at: str
  source: str
  kind: str = "generic"  # evento | nota | recordatorio | inmediata | generic
  seen_by_owner: bool = False
  severity: str = "normal"  # normal | high | critical
  is_duplicate: bool = False
  duplicate_of: str = ""


def _load_state() -> dict:
  if not DATA_PATH.exists():
    return {"urgencias": []}
  try:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))
  except Exception:
    # fallback defensivo
    return {"urgencias": []}


def _save_state(state: dict) -> None:
  DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
  DATA_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def mensaje_contiene_urgencia(text: str) -> bool:
  if not text:
    return False
  lowered = text.lower()
  return "urgente" in lowered or "urgencia" in lowered


def _parse_iso_dt(value: str) -> Optional[datetime]:
  try:
    return datetime.fromisoformat(value)
  except Exception:
    return None


def _normalize_text(value: str) -> str:
  return " ".join((value or "").strip().lower().split())


def _severity_for_kind(kind: str) -> str:
  if kind == "inmediata":
    return "critical"
  if kind in {"evento", "recordatorio"}:
    return "high"
  return "normal"


def _find_recent_duplicate(state: dict, from_msisdn: str, text: str, kind: str) -> Optional[dict]:
  normalized = _normalize_text(text)
  if not normalized:
    return None
  now = datetime.now(timezone.utc)

  for raw in reversed(state.get("urgencias", [])):
    if raw.get("from_msisdn") != from_msisdn:
      continue
    if raw.get("kind") != kind:
      continue
    prev_norm = _normalize_text(raw.get("text", ""))
    if prev_norm != normalized:
      similarity = SequenceMatcher(a=prev_norm, b=normalized).ratio()
      if similarity < SEMANTIC_SIMILARITY_THRESHOLD:
        continue

    created = _parse_iso_dt(raw.get("created_at", ""))
    if created is None:
      continue
    if created.tzinfo is None:
      created = created.replace(tzinfo=timezone.utc)

    if now - created <= timedelta(seconds=DEDUP_WINDOW_SECONDS):
      return raw

  return None


def registrar_urgencia(from_msisdn: str, text: str, source: str = "whatsapp", kind: str = "generic") -> Urgencia:
  state = _load_state()
  duplicate = _find_recent_duplicate(state, from_msisdn=from_msisdn, text=text, kind=kind)

  if duplicate is not None:
    return Urgencia(
      id=duplicate.get("id", ""),
      from_msisdn=duplicate.get("from_msisdn", from_msisdn),
      text=duplicate.get("text", text),
      created_at=duplicate.get("created_at", datetime.now(timezone.utc).isoformat()),
      source=duplicate.get("source", source),
      kind=duplicate.get("kind", kind),
      seen_by_owner=duplicate.get("seen_by_owner", False),
      severity=duplicate.get("severity", _severity_for_kind(kind)),
      is_duplicate=True,
      duplicate_of=duplicate.get("id", ""),
    )

  urg_id = f"urg-{uuid.uuid4().hex[:10]}"
  now_iso = datetime.now(timezone.utc).isoformat()
  urg = Urgencia(
    id=urg_id,
    from_msisdn=from_msisdn,
    text=text,
    created_at=now_iso,
    source=source,
    kind=kind,
    severity=_severity_for_kind(kind),
  )
  state.setdefault("urgencias", []).append(urg.__dict__)
  _save_state(state)
  return urg


def construir_alerta_para_owner(urg: Urgencia) -> str:
  header = "🚨 URGENCIA VIP"
  if urg.kind and urg.kind != "generic":
    header += f" ({urg.kind})"
  if urg.severity == "critical":
    header += " [CRITICA]"
  if urg.is_duplicate:
    header += " [DUPLICADA]"
  return (
    f"{header}\n"
    f"Hora (UTC): {urg.created_at}\n"
    f"Severidad: {urg.severity}\n"
    f"Texto: {urg.text}\n\n"
    f"Por favor revisa el chat con el VIP ahora mismo."
  )


def manejar_urgencia(from_msisdn: str, text: str, source: str = "whatsapp", kind: str = "generic") -> str:
  """Registra la urgencia y devuelve el texto de alerta para el owner.

  No hace envíos directos; la capa superior decide cómo mandar el mensaje.
  """
  urg = registrar_urgencia(from_msisdn=from_msisdn, text=text, source=source, kind=kind)
  return construir_alerta_para_owner(urg)
