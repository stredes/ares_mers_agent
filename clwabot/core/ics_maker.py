from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytz

TZ = pytz.timezone("America/Santiago")
BASE_DIR = Path(__file__).resolve().parent.parent
CAL_DIR = BASE_DIR / "calendar"
CAL_DIR.mkdir(parents=True, exist_ok=True)


def make_ics(
    title: str,
    start: datetime,
    duration_minutes: int = 60,
    description: str | None = None,
    location: str | None = None,
) -> Path:
    """Genera un archivo .ics simple y lo guarda en clwabot/calendar/.

    Todos los tiempos se manejan como timezone-aware en America/Santiago
    y se exportan en formato UTC como recomienda iCalendar.
    """

    if start.tzinfo is None:
        start = TZ.localize(start)
    else:
        start = start.astimezone(TZ)

    end = start + timedelta(minutes=duration_minutes)

    uid = f"{uuid.uuid4()}@clwabot"
    dtstamp = datetime.now(tz=TZ).astimezone(pytz.UTC).strftime("%Y%m%dT%H%M%SZ")

    dtstart_utc = start.astimezone(pytz.UTC).strftime("%Y%m%dT%H%M%SZ")
    dtend_utc = end.astimezone(pytz.UTC).strftime("%Y%m%dT%H%M%SZ")

    # iCalendar básico, idioma libre (usaremos ES en los textos)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//clwabot//ares_mers//ES",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{dtstart_utc}",
        f"DTEND:{dtend_utc}",
        f"SUMMARY:{title}",
    ]

    if description:
        # Sustituimos saltos de línea por \n escapado
        desc = description.replace("\n", "\\n")
        lines.append(f"DESCRIPTION:{desc}")

    if location:
        lines.append(f"LOCATION:{location}")

    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    content = "\r\n".join(lines) + "\r\n"

    # Nombre de archivo: YYYYMMDD_HHMM_summary_simplificada.ics
    ts = start.strftime("%Y%m%d_%H%M")
    safe_title = "".join(c for c in title if c.isalnum() or c in ("-", "_")).strip()
    if not safe_title:
        safe_title = "evento"
    filename = f"{ts}_{safe_title}.ics"

    out_path = CAL_DIR / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


def demo():  # función de prueba manual
    start = TZ.localize(datetime.now() + timedelta(hours=1))
    path = make_ics(
        title="Reunión OSCP de prueba",
        start=start,
        duration_minutes=60,
        description="Revisar lab de privesc Windows.",
        location="Online",
    )
    print(str(path))


if __name__ == "__main__":
    demo()
