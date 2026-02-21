import json
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_OSCP = BASE_DIR / "config" / "oscp.yaml"


def load_config():
    with open(CONFIG_OSCP, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_study_plan():
    cfg = load_config()
    hours = cfg["profile"].get("hours_per_week", 10)
    enrolled = cfg["profile"].get("enrolled", False)

    # Plan muy simple: luego lo afinamos con Ares en la conversación
    plan = {
        "enrolled": enrolled,
        "hours_per_week": hours,
        "phases": [
            {
                "name": "Fundamentos y Recon",
                "focus": ["TCP/IP", "Linux basics", "nmap", "web basics"],
            },
            {
                "name": "Explotación y privesc",
                "focus": ["Linux privesc", "Windows privesc", "password attacks"],
            },
            {
                "name": "Active Directory y lab exam-like",
                "focus": ["AD basics", "BloodHound", "kerberoasting", "lateral movement"],
            },
        ],
    }
    return plan


def main():
    plan = generate_study_plan()
    print(json.dumps(plan, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
