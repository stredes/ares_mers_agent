import json
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_CONTACTS = BASE_DIR / "config" / "contacts.yaml"
STATE_PATH = BASE_DIR / "data" / "state.json"


def load_contacts():
    with open(CONFIG_CONTACTS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    if not STATE_PATH.exists():
        return {"vip": {"last_morning_sent": {}}, "reports": {"last_daily_report": None}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def should_send_morning(contact, now=None):
    if now is None:
        now = datetime.now()

    cfg = load_contacts()
    vip_list = cfg.get("vip_contacts", [])
    target = next((v for v in vip_list if v["number"] == contact), None)
    if not target:
        return False, None

    mm = target.get("morning_message", {})
    if not mm.get("enabled", False):
        return False, None

    # TODO: respetar timezone desde config; por ahora usamos hora local
    target_time = mm.get("time", "08:30")
    hh, m = map(int, target_time.split(":"))

    state = load_state()
    last_sent = state["vip"]["last_morning_sent"].get(contact)
    today = now.strftime("%Y-%m-%d")

    # solo enviar si no se envió hoy y estamos en/tras la hora objetivo
    if last_sent == today:
        return False, None

    if now.hour > hh or (now.hour == hh and now.minute >= m):
        text = mm.get("text", "Buenos días")
        state["vip"]["last_morning_sent"][contact] = today
        save_state(state)
        return True, text

    return False, None


if __name__ == "__main__":
    ok, text = should_send_morning("+56975551112")
    if ok:
        print(text)
