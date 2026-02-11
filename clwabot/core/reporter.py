import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "data" / "state.json"
REPORTS_DIR = BASE_DIR / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_state():
    if not STATE_PATH.exists():
        return {"vip": {"last_morning_sent": {}}, "reports": {"last_daily_report": None}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def generate_daily_report(summary=None):
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d_%H-%M-%S")
    date_str = now.strftime("%Y-%m-%d")

    if summary is None:
        # Placeholder: luego lo alimentamos con datos reales (cuando tengamos integraciones)
        summary = {
            "total_events": 0,
            "inbound": 0,
            "outbound": 0,
            "top_contact": None,
            "top_topic": None,
            "pending": [],
        }

    report_text = f"""[REPORTE TÁCTICO DIARIO - ares_mers]
Misión: Monitoreo de Comunicaciones stredes
Fecha: {date_str} | Status: OPERATIVO

--- RESUMEN DE ACTIVIDAD ---
Total Eventos: {summary['total_events']}
📥 Inbound: {summary['inbound']} | 📤 Outbound: {summary['outbound']}

--- OBJETIVOS PRIORITARIOS (Sin Respuesta) ---
"""

    if summary["pending"]:
        for i, p in enumerate(summary["pending"], start=1):
            report_text += f"{i}. {p}\n"
    else:
        report_text += "(Ninguno registrado)\n"

    report_text += "\n--- ANÁLISIS DE TRÁFICO ---\n"
    report_text += f"Top Contacto: {summary['top_contact']}\n"
    report_text += f"Tema Dominante: {summary['top_topic']}\n\n"
    report_text += "--- NOTA DEL AGENTE ---\n"
    report_text += "stredes, la actividad hoy ha sido registrada. Try Harder.\n"

    out_path = REPORTS_DIR / f"daily_report_{ts}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    state = load_state()
    state["reports"]["last_daily_report"] = date_str
    save_state(state)

    print(report_text)


if __name__ == "__main__":
    generate_daily_report()
