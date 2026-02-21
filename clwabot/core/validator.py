from dataclasses import dataclass
from typing import Literal

from .urgencia_handler import mensaje_contiene_urgencia

OWNER_MSISDN = "+56954764325"
VIP_MSISDN = "+56975551112"

Role = Literal["owner", "vip", "other"]


@dataclass
class ValidationResult:
  role: Role
  can_reply: bool
  is_urgency: bool


def validate_message(msisdn: str, text: str) -> ValidationResult:
  """Aplica las reglas centrales de routing.

  - owner  → siempre se puede responder libremente
  - vip    → solo se permite flujo si hay "urgente/urgencia"
  - other  → silencio total
  """
  if msisdn == OWNER_MSISDN:
    return ValidationResult(role="owner", can_reply=True, is_urgency=False)

  if msisdn == VIP_MSISDN:
    is_urg = mensaje_contiene_urgencia(text or "")
    return ValidationResult(role="vip", can_reply=is_urg, is_urgency=is_urg)

  # cualquier otro número
  return ValidationResult(role="other", can_reply=False, is_urgency=False)
