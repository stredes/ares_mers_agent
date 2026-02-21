from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Dict, Literal, Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_OSCP = BASE_DIR / "config" / "oscp.yaml"
LabStatus = Literal["pending", "in_progress", "rooted"]

DEFAULT_CFG = {
    "profile": {"name": "stredes", "enrolled": False, "hours_per_week": 10},
    "platforms": [],
    "weak_spots": [],
    "labs": [],
}


def load_config():
    if not CONFIG_OSCP.exists():
        return dict(DEFAULT_CFG)
    with open(CONFIG_OSCP, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _merge_defaults(raw)


def save_config(cfg: dict) -> None:
    CONFIG_OSCP.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_OSCP, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def _merge_defaults(raw: dict) -> dict:
    cfg = dict(DEFAULT_CFG)
    cfg.update(raw)
    cfg["profile"] = {**DEFAULT_CFG["profile"], **(raw.get("profile") or {})}
    cfg["platforms"] = raw.get("platforms") or []
    cfg["weak_spots"] = raw.get("weak_spots") or []
    cfg["labs"] = raw.get("labs") or []
    return cfg


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text or "")
    clean = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return " ".join(clean.lower().split())


def _find_lab(cfg: dict, name: str) -> Optional[Dict]:
    query = _normalize(name)
    if not query:
        return None
    for lab in cfg.get("labs", []):
        lab_name = str(lab.get("name", "")).strip()
        if _normalize(lab_name) == query:
            return lab
    for lab in cfg.get("labs", []):
        lab_name = str(lab.get("name", "")).strip()
        if query in _normalize(lab_name):
            return lab
    return None


def _stats(cfg: dict) -> dict:
    labs = cfg.get("labs", [])
    total = len(labs)
    pending = sum(1 for l in labs if l.get("status", "pending") == "pending")
    in_progress = sum(1 for l in labs if l.get("status", "pending") == "in_progress")
    rooted = sum(1 for l in labs if l.get("status", "pending") == "rooted")
    progress = int((rooted / total) * 100) if total else 0
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "rooted": rooted,
        "progress_percent": progress,
    }


def generate_study_plan():
    cfg = load_config()
    hours = int(cfg["profile"].get("hours_per_week", 10) or 10)
    enrolled = cfg["profile"].get("enrolled", False)
    weak_spots = cfg.get("weak_spots", [])
    phase_a = round(hours * 0.30, 1)
    phase_b = round(hours * 0.45, 1)
    phase_c = round(hours - phase_a - phase_b, 1)

    plan = {
        "enrolled": enrolled,
        "hours_per_week": hours,
        "weak_spots": weak_spots,
        "phases": [
            {
                "name": "Fundamentos y Recon",
                "hours": phase_a,
                "focus": ["enumeración", "nmap", "web basics", "scripting básico"],
            },
            {
                "name": "Explotación y privesc",
                "hours": phase_b,
                "focus": ["Linux privesc", "Windows privesc", "password attacks", "pivoting"],
            },
            {
                "name": "Active Directory y lab exam-like",
                "hours": phase_c,
                "focus": ["AD basics", "BloodHound", "kerberoasting", "lateral movement", "reporte"],
            },
        ],
    }
    return plan


def get_next_action() -> str:
    cfg = load_config()
    weak_spots = cfg.get("weak_spots", [])
    active = next((l for l in cfg.get("labs", []) if l.get("status") == "in_progress"), None)
    if active:
        return f"Continúa el lab activo: {active.get('name', 'lab')} ({active.get('platform', 'N/A')})."

    pending = next((l for l in cfg.get("labs", []) if l.get("status", "pending") == "pending"), None)
    if pending:
        focus = weak_spots[0] if weak_spots else "enumeración inicial"
        return (
            f"Siguiente objetivo: iniciar {pending.get('name', 'lab')} "
            f"en {pending.get('platform', 'N/A')} y enfocarte en {focus}."
        )

    if weak_spots:
        return f"No hay labs pendientes. Entrena específicamente: {', '.join(weak_spots[:2])}."
    return "No hay labs cargados. Agrega uno para iniciar el entrenamiento."


def format_status_text() -> str:
    cfg = load_config()
    prof = cfg.get("profile", {})
    stats = _stats(cfg)
    weak_spots = cfg.get("weak_spots", [])
    return (
        "OSCP status\n"
        f"- perfil: {prof.get('name', 'N/A')}\n"
        f"- inscrito: {prof.get('enrolled', False)}\n"
        f"- horas/semana: {prof.get('hours_per_week', 10)}\n"
        f"- labs: {stats['rooted']}/{stats['total']} rooted ({stats['progress_percent']}%)\n"
        f"- en curso: {stats['in_progress']} | pendientes: {stats['pending']}\n"
        f"- weak spots: {', '.join(weak_spots[:3]) if weak_spots else 'sin definir'}"
    )


def format_plan_text() -> str:
    plan = generate_study_plan()
    phases = plan.get("phases", [])
    lines = [
        "OSCP plan semanal",
        f"- horas totales: {plan.get('hours_per_week', 10)}",
    ]
    if plan.get("weak_spots"):
        lines.append(f"- focos débiles: {', '.join(plan['weak_spots'][:3])}")
    for ph in phases:
        focus = ", ".join(ph.get("focus", [])[:4])
        lines.append(f"- {ph.get('name')}: {ph.get('hours', 0)}h ({focus})")
    return "\n".join(lines)


def format_labs_text(limit: int = 8) -> str:
    cfg = load_config()
    labs = cfg.get("labs", [])
    if not labs:
        return "No hay labs cargados en oscp.yaml."
    rows = ["OSCP labs (top):"]
    for lab in labs[: max(1, limit)]:
        rows.append(
            f"- {lab.get('name', 'N/A')} | {lab.get('platform', 'N/A')} | "
            f"{lab.get('status', 'pending')} | {lab.get('ip', '-')}"
        )
    return "\n".join(rows)


def set_lab_status(lab_name: str, status: LabStatus) -> str:
    cfg = load_config()
    lab = _find_lab(cfg, lab_name)
    if not lab:
        return f"No encontré el lab '{lab_name}'."
    lab["status"] = status
    save_config(cfg)
    return f"Lab actualizado: {lab.get('name')} -> {status}"


def add_lab_note(lab_name: str, note: str) -> str:
    cfg = load_config()
    lab = _find_lab(cfg, lab_name)
    if not lab:
        return f"No encontré el lab '{lab_name}'."
    notes = lab.setdefault("notes", [])
    notes.append(note.strip())
    if len(notes) > 20:
        del notes[:-20]
    save_config(cfg)
    return f"Nota agregada a {lab.get('name')}."


def main():
    plan = generate_study_plan()
    print(json.dumps(plan, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
