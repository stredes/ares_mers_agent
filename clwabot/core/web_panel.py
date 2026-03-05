#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .meeting_session import get_active_meeting_session
from .state_store import load_state, save_state
from .urgencia_session import get_active_session

BASE_DIR = Path(__file__).resolve().parent.parent
URGENCIAS_PATH = BASE_DIR / "data" / "urgencias.json"
QUEUE_PATH = BASE_DIR / "data" / "google_calendar_queue.json"
REPORTS_DIR = BASE_DIR / "data" / "reports"
MODE_OPTIONS = {"normal", "busy", "vacation"}
MEETING_STATUS_OPTIONS = {"pending", "confirmed", "past", "dismissed"}
SERVICE_ACTIONS = {"start", "stop", "restart"}
SERVICE_ALLOWLIST = {"openclaw-gateway.service", "clwabot-router.service"}


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, code: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _compact(text: str, limit: int = 140) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _service_status(name: str) -> str:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return "unknown"
    return (proc.stdout or "").strip() or "unknown"


def _service_action(name: str, action: str) -> tuple[bool, str]:
    if name not in SERVICE_ALLOWLIST or action not in SERVICE_ACTIONS:
        return False, "service/action not allowed"
    try:
        proc = subprocess.run(
            ["systemctl", "--user", action, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "failed").strip()
    return True, "ok"


def _build_urgencias(range_days: int, kind: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, min(365, range_days)))
    raw = _load_json(URGENCIAS_PATH, {"urgencias": {}}).get("urgencias", [])
    rows = []
    for item in raw:
        created = _parse_iso(item.get("created_at", ""))
        if created is None or created < cutoff:
            continue
        row_kind = item.get("kind", "generic")
        if kind != "all" and row_kind != kind:
            continue
        ics_path = item.get("ics_path", "")
        rows.append(
            {
                "id": item.get("id", ""),
                "created_at": item.get("created_at", ""),
                "kind": row_kind,
                "severity": item.get("severity", "normal"),
                "seen_by_owner": bool(item.get("seen_by_owner", False)),
                "text": item.get("text", ""),
                "summary": _compact(item.get("text", "")),
                "ics_path": ics_path,
                "ics_download": f"/api/ics?path={urllib.parse.quote(ics_path)}" if ics_path else "",
            }
        )
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return rows


def _build_meetings() -> list[dict]:
    events = _load_json(QUEUE_PATH, {"events": []}).get("events", [])
    now = datetime.now(timezone.utc)
    rows = []
    for idx, ev in enumerate(events):
        start = _parse_iso(ev.get("start_iso", ""))
        status = (ev.get("status") or "pending").lower()
        if status not in MEETING_STATUS_OPTIONS:
            status = "pending"
        if status == "pending" and start and start < now:
            status = "past"
        ics_path = ev.get("ics_path", "")
        rows.append(
            {
                "id": ev.get("created_at", f"meeting-{idx}"),
                "queue_index": idx,
                "created_at": ev.get("created_at", ""),
                "contact": ev.get("msisdn", ""),
                "title": ev.get("title", "Reunión"),
                "topic": ev.get("title", "Reunión").replace("Reunión: ", ""),
                "start_iso": ev.get("start_iso", ""),
                "status": status,
                "location": ev.get("location", ""),
                "ics_path": ics_path,
                "ics_download": f"/api/ics?path={urllib.parse.quote(ics_path)}" if ics_path else "",
            }
        )
    rows.sort(key=lambda x: x.get("start_iso", ""), reverse=True)
    return rows


def _build_timeline(limit: int = 40) -> list[dict]:
    state = load_state()
    events = []
    for ev in state.get("metrics", {}).get("events", []):
        at = ev.get("at", "")
        kind = ev.get("kind", "metric")
        events.append({"at": at, "kind": kind, "summary": _compact(json.dumps(ev, ensure_ascii=False), 180)})

    for u in _load_json(URGENCIAS_PATH, {"urgencias": []}).get("urgencias", []):
        events.append(
            {
                "at": u.get("created_at", ""),
                "kind": "urgencia",
                "summary": f"{u.get('kind', 'generic')}: {_compact(u.get('text', ''), 120)}",
            }
        )

    for ev in _load_json(QUEUE_PATH, {"events": []}).get("events", []):
        events.append(
            {
                "at": ev.get("created_at", ""),
                "kind": "meeting",
                "summary": f"{ev.get('title', 'Reunión')} ({ev.get('start_iso', '-')})",
            }
        )

    for path in sorted(REPORTS_DIR.glob("*.txt"), reverse=True)[:5]:
        events.append({"at": path.stem, "kind": "report", "summary": f"Reporte generado: {path.name}"})

    events.sort(key=lambda x: x.get("at", ""), reverse=True)
    return events[: max(1, min(limit, 200))]


def _build_status(range_days: int, kind: str) -> dict:
    state = load_state()
    contacts = state.get("contacts", {})
    urgencias = _build_urgencias(range_days=range_days, kind=kind)
    meetings = _build_meetings()
    weekly_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    weekly_urg = [
        u
        for u in _build_urgencias(range_days=7, kind="all")
        if (_parse_iso(u.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= weekly_cutoff
    ]

    by_kind = {}
    for u in weekly_urg:
        by_kind[u["kind"]] = by_kind.get(u["kind"], 0) + 1

    payload = {
        "assistant": state.get("assistant", {}),
        "contacts_total": len(contacts),
        "active_urgencias": [msisdn for msisdn in contacts if get_active_session(msisdn)],
        "active_meetings": [msisdn for msisdn in contacts if get_active_meeting_session(msisdn)],
        "metrics_count": len(state.get("metrics", {}).get("events", [])),
        "urgencias": urgencias,
        "urgencias_week": {
            "total": len(weekly_urg),
            "immediatas": by_kind.get("inmediata", 0),
            "eventos": by_kind.get("evento", 0),
            "notas": by_kind.get("nota", 0),
            "recordatorios": by_kind.get("recordatorio", 0),
        },
        "meetings": meetings,
        "timeline": _build_timeline(),
        "services": {
            "openclaw_gateway": _service_status("openclaw-gateway.service"),
            "clwabot_router": _service_status("clwabot-router.service"),
        },
    }
    return payload


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0") or 0)
    except Exception:
        return {}
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


class Handler(BaseHTTPRequestHandler):
    def _route(self) -> tuple[str, dict]:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        flat = {k: v[-1] for k, v in params.items() if v}
        return parsed.path, flat

    def do_GET(self):  # noqa: N802
        path, query = self._route()
        if path not in {"/", "/status.json", "/api/status", "/api/ics"}:
            self.send_response(404)
            self.end_headers()
            return

        if path == "/api/ics":
            ics_path = query.get("path", "")
            if not ics_path:
                _json_response(self, {"ok": False, "error": "missing path"}, code=400)
                return
            p = Path(urllib.parse.unquote(ics_path))
            if p.suffix.lower() != ".ics" or not p.exists() or not p.is_file():
                _json_response(self, {"ok": False, "error": "invalid file"}, code=404)
                return
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        days = int(query.get("days", "7") or "7")
        kind = query.get("kind", "all")
        payload = _build_status(range_days=days, kind=kind)
        if path in {"/status.json", "/api/status"}:
            _json_response(self, payload)
            return

        html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>clwabot command center</title>
  <style>
    :root { --bg:#0d1117; --card:#161b22; --text:#e6edf3; --muted:#8b949e; --ok:#3fb950; --warn:#d29922; --bad:#f85149; --accent:#58a6ff; }
    body { margin:0; font-family: "JetBrains Mono", "Fira Code", monospace; background: radial-gradient(circle at 20% 0%, #1f2a3a 0%, var(--bg) 38%); color: var(--text); }
    .wrap { max-width: 1280px; margin: 0 auto; padding: 20px; }
    h1 { margin: 0 0 10px; font-size: 24px; }
    .muted { color: var(--muted); }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); gap:12px; margin: 14px 0 22px; }
    .card { background: var(--card); border:1px solid #30363d; border-radius:12px; padding:12px; }
    .kpi { font-size:26px; font-weight:700; }
    .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:8px 0; }
    input, select, button { background:#0b0f14; color:var(--text); border:1px solid #30363d; border-radius:8px; padding:8px 10px; }
    button { cursor:pointer; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { border-bottom:1px solid #2b3138; padding:8px; text-align:left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    .pill { padding:2px 8px; border-radius:999px; border:1px solid #30363d; }
    .ok { color: var(--ok); } .warn { color: var(--warn); } .bad { color: var(--bad); }
    .timeline { max-height: 320px; overflow: auto; }
    .timeline li { margin-bottom: 8px; }
    a { color: var(--accent); }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>ARES / clwabot - Command Center</h1>
    <div class="muted">VIP urgencias, reuniones, control del asistente, timeline y estado de servicios</div>
    <div id="app"></div>
  </div>
<script>
async function api(url, method="GET", body=null){
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if(body){ opt.body = JSON.stringify(body); }
  const r = await fetch(url, opt);
  return await r.json();
}

function serviceClass(status){
  if(status==="active") return "ok";
  if(status==="inactive" || status==="failed") return "bad";
  return "warn";
}

function esc(v){
  return String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

function render(data){
  const app = document.getElementById("app");
  const u = data.urgencias_week || {};
  app.innerHTML = `
    <div class="grid">
      <div class="card"><div class="muted">Urgencias semana</div><div class="kpi">${u.total ?? 0}</div></div>
      <div class="card"><div class="muted">Inmediatas</div><div class="kpi">${u.inmediatas ?? 0}</div></div>
      <div class="card"><div class="muted">Eventos</div><div class="kpi">${u.eventos ?? 0}</div></div>
      <div class="card"><div class="muted">Reuniones</div><div class="kpi">${(data.meetings || []).length}</div></div>
      <div class="card"><div class="muted">Gateway</div><div class="pill ${serviceClass(data.services.openclaw_gateway)}">${esc(data.services.openclaw_gateway)}</div></div>
      <div class="card"><div class="muted">Router</div><div class="pill ${serviceClass(data.services.clwabot_router)}">${esc(data.services.clwabot_router)}</div></div>
    </div>

    <div class="card">
      <h3>Servicios</h3>
      <div class="row">
        <button onclick="serviceAction('openclaw-gateway.service','restart')">Restart gateway</button>
        <button onclick="serviceAction('clwabot-router.service','restart')">Restart router</button>
        <button onclick="serviceAction('clwabot-router.service','stop')">Stop router</button>
        <button onclick="serviceAction('clwabot-router.service','start')">Start router</button>
      </div>
    </div>

    <div class="card">
      <h3>Control de modos</h3>
      <div class="row">
        <label>Modo</label>
        <select id="mode">
          <option value="normal">normal</option>
          <option value="busy">busy</option>
          <option value="vacation">vacation</option>
        </select>
        <button onclick="setMode()">Guardar</button>
      </div>
      <div class="row">
        <label>Horario</label>
        <input id="start" value="${esc(data.assistant?.business_hours?.start || "09:00")}">
        <input id="end" value="${esc(data.assistant?.business_hours?.end || "19:00")}">
        <button onclick="setHours()">Guardar</button>
      </div>
      <div class="row">
        <label><input type="checkbox" id="tg_morning"> buenos días VIP</label>
        <label><input type="checkbox" id="tg_meeting"> auto-reuniones</label>
        <label><input type="checkbox" id="tg_urgency"> protocolo urgencia</label>
        <button onclick="setToggles()">Guardar toggles</button>
      </div>
    </div>

    <div class="card">
      <h3>Urgencias VIP</h3>
      <div class="row">
        <select id="days"><option value="1">24h</option><option value="7">7 días</option><option value="30">30 días</option></select>
        <select id="kind"><option value="all">todos</option><option value="evento">evento</option><option value="nota">nota</option><option value="recordatorio">recordatorio</option><option value="inmediata">inmediata</option></select>
        <button onclick="reloadFiltered()">Filtrar</button>
      </div>
      <table><thead><tr><th>Hora</th><th>Tipo</th><th>Texto</th><th>Estado</th><th>ICS</th><th>Acción</th></tr></thead><tbody>
      ${(data.urgencias || []).map(x => `
        <tr>
          <td>${esc(x.created_at)}</td>
          <td>${esc(x.kind)}</td>
          <td>${esc(x.summary)}</td>
          <td>${x.seen_by_owner ? "atendida" : "pendiente"}</td>
          <td>${x.ics_download ? `<a href="${esc(x.ics_download)}">descargar</a>` : "-"}</td>
          <td>${!x.seen_by_owner ? `<button onclick="markUrgSeen('${esc(x.id)}')">marcar atendida</button>` : ""}</td>
        </tr>`).join("")}
      </tbody></table>
    </div>

    <div class="card">
      <h3>Reuniones externas</h3>
      <table><thead><tr><th>Contacto</th><th>Inicio</th><th>Tema</th><th>Estado</th><th>ICS</th><th>Acción</th></tr></thead><tbody>
      ${(data.meetings || []).map(x => `
        <tr>
          <td>${esc(x.contact)}</td>
          <td>${esc(x.start_iso)}</td>
          <td>${esc(x.topic)}</td>
          <td>${esc(x.status)}</td>
          <td>${x.ics_download ? `<a href="${esc(x.ics_download)}">descargar</a>` : "-"}</td>
          <td>
            <button onclick="setMeetingStatus(${x.queue_index}, 'confirmed')">confirmada</button>
            <button onclick="setMeetingStatus(${x.queue_index}, 'dismissed')">atendida</button>
          </td>
        </tr>`).join("")}
      </tbody></table>
    </div>

    <div class="card">
      <h3>Timeline</h3>
      <ul class="timeline">
      ${(data.timeline || []).map(x => `<li><span class="muted">${esc(x.at)}</span> <b>${esc(x.kind)}</b> ${esc(x.summary)}</li>`).join("")}
      </ul>
    </div>
  `;

  const mode = document.getElementById("mode");
  if(mode){ mode.value = data.assistant?.mode || "normal"; }
  const f = data.assistant?.features || {};
  document.getElementById("tg_morning").checked = f.good_morning_vip !== false;
  document.getElementById("tg_meeting").checked = f.auto_meetings !== false;
  document.getElementById("tg_urgency").checked = f.urgency_protocol !== false;
}

async function refresh(){
  const data = await api("/api/status");
  render(data);
}

async function reloadFiltered(){
  const d = document.getElementById("days").value;
  const k = document.getElementById("kind").value;
  const data = await api(`/api/status?days=${encodeURIComponent(d)}&kind=${encodeURIComponent(k)}`);
  render(data);
}

async function setMode(){
  const mode = document.getElementById("mode").value;
  await api("/api/assistant/mode", "POST", { mode });
  await refresh();
}

async function setHours(){
  const start = document.getElementById("start").value;
  const end = document.getElementById("end").value;
  await api("/api/assistant/hours", "POST", { start, end });
  await refresh();
}

async function setToggles(){
  await api("/api/assistant/toggles", "POST", {
    good_morning_vip: document.getElementById("tg_morning").checked,
    auto_meetings: document.getElementById("tg_meeting").checked,
    urgency_protocol: document.getElementById("tg_urgency").checked
  });
  await refresh();
}

async function markUrgSeen(id){
  await api("/api/urgencias/seen", "POST", { id });
  await refresh();
}

async function setMeetingStatus(queue_index, status){
  await api("/api/meetings/status", "POST", { queue_index, status });
  await refresh();
}

async function serviceAction(service, action){
  await api("/api/services/action", "POST", { service, action });
  await refresh();
}

refresh();
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        path, _ = self._route()
        body = _read_json_body(self)
        state = load_state()
        assistant = state.setdefault("assistant", {})
        assistant.setdefault("business_hours", {"start": "09:00", "end": "19:00", "timezone": "America/Santiago"})
        features = assistant.setdefault(
            "features",
            {"good_morning_vip": True, "auto_meetings": True, "urgency_protocol": True},
        )

        if path == "/api/assistant/mode":
            mode = str(body.get("mode", "")).strip().lower()
            if mode not in MODE_OPTIONS:
                _json_response(self, {"ok": False, "error": "invalid mode"}, code=400)
                return
            assistant["mode"] = mode
            save_state(state)
            _json_response(self, {"ok": True, "mode": mode})
            return

        if path == "/api/assistant/hours":
            start = str(body.get("start", "")).strip()
            end = str(body.get("end", "")).strip()
            if len(start) != 5 or len(end) != 5 or ":" not in start or ":" not in end:
                _json_response(self, {"ok": False, "error": "invalid HH:MM"}, code=400)
                return
            assistant["business_hours"]["start"] = start
            assistant["business_hours"]["end"] = end
            save_state(state)
            _json_response(self, {"ok": True, "start": start, "end": end})
            return

        if path == "/api/assistant/toggles":
            for key in ("good_morning_vip", "auto_meetings", "urgency_protocol"):
                if key in body:
                    features[key] = bool(body[key])
            save_state(state)
            _json_response(self, {"ok": True, "features": features})
            return

        if path == "/api/urgencias/seen":
            urg_id = str(body.get("id", "")).strip()
            data = _load_json(URGENCIAS_PATH, {"urgencias": []})
            found = False
            for row in data.get("urgencias", []):
                if row.get("id") == urg_id:
                    row["seen_by_owner"] = True
                    found = True
                    break
            if not found:
                _json_response(self, {"ok": False, "error": "urgencia not found"}, code=404)
                return
            _save_json(URGENCIAS_PATH, data)
            _json_response(self, {"ok": True, "id": urg_id})
            return

        if path == "/api/meetings/status":
            try:
                idx = int(body.get("queue_index", -1))
            except Exception:
                idx = -1
            status = str(body.get("status", "")).strip().lower()
            if status not in MEETING_STATUS_OPTIONS:
                _json_response(self, {"ok": False, "error": "invalid status"}, code=400)
                return
            data = _load_json(QUEUE_PATH, {"events": []})
            events = data.get("events", [])
            if idx < 0 or idx >= len(events):
                _json_response(self, {"ok": False, "error": "invalid queue_index"}, code=400)
                return
            events[idx]["status"] = status
            _save_json(QUEUE_PATH, data)
            _json_response(self, {"ok": True, "queue_index": idx, "status": status})
            return

        if path == "/api/services/action":
            service = str(body.get("service", "")).strip()
            action = str(body.get("action", "")).strip()
            ok, detail = _service_action(service, action)
            code = 200 if ok else 400
            _json_response(self, {"ok": ok, "service": service, "action": action, "detail": detail}, code=code)
            return

        _json_response(self, {"ok": False, "error": "not found"}, code=404)

    def log_message(self, fmt: str, *args):  # noqa: A003
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="clwabot command center")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"clwabot web panel listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
