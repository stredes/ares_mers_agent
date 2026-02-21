from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, request

from clwabot.core.web_panel import _build_status

app = Flask(__name__)


def _clean_for_cloud(payload: dict) -> dict:
    """Sanitiza campos que en Vercel no son operables (systemd / rutas locales)."""
    payload = dict(payload)
    payload["services"] = {
        "openclaw_gateway": "n/a-cloud",
        "clwabot_router": "n/a-cloud",
    }

    meetings = []
    for m in payload.get("meetings", []):
        row = dict(m)
        ics_path = row.get("ics_path", "")
        if not ics_path or not Path(ics_path).exists():
            row["ics_download"] = ""
        meetings.append(row)
    payload["meetings"] = meetings

    urgencias = []
    for u in payload.get("urgencias", []):
        row = dict(u)
        ics_path = row.get("ics_path", "")
        if not ics_path or not Path(ics_path).exists():
            row["ics_download"] = ""
        urgencias.append(row)
    payload["urgencias"] = urgencias
    return payload


@app.get("/")
def home():
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ARES Cloud Panel</title>
  <style>
    body { font-family: ui-monospace, Menlo, monospace; max-width: 1200px; margin: 16px auto; padding: 0 12px; background:#0f1116; color:#e6edf3; }
    .muted{ color:#97a0ab; } .card{ border:1px solid #2f353d; border-radius:10px; padding:12px; margin-bottom:12px; background:#171b22; }
    .grid{ display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap:10px; }
    table{ width:100%; border-collapse: collapse; font-size:13px; } th,td{ border-bottom:1px solid #2b3138; padding:7px; text-align:left; }
    a{ color:#58a6ff; }
  </style>
</head>
<body>
  <h2>ARES / clwabot Cloud Panel</h2>
  <div class="muted">Modo cloud (solo lectura). Controles de systemd se usan en panel local.</div>
  <div id="app" class="card">Cargando...</div>
<script>
async function load(){
  const res = await fetch('/api/status?days=7&kind=all');
  const d = await res.json();
  const wk = d.urgencias_week || {};
  document.getElementById('app').innerHTML = `
    <div class="grid">
      <div class="card"><div class="muted">Urgencias semana</div><div>${wk.total ?? 0}</div></div>
      <div class="card"><div class="muted">Inmediatas</div><div>${wk.inmediatas ?? 0}</div></div>
      <div class="card"><div class="muted">Eventos</div><div>${wk.eventos ?? 0}</div></div>
      <div class="card"><div class="muted">Reuniones</div><div>${(d.meetings||[]).length}</div></div>
    </div>
    <div class="card">
      <b>Urgencias</b>
      <table><thead><tr><th>Hora</th><th>Tipo</th><th>Texto</th><th>Estado</th></tr></thead><tbody>
      ${(d.urgencias||[]).map(x=>`<tr><td>${x.created_at||''}</td><td>${x.kind||''}</td><td>${x.summary||''}</td><td>${x.seen_by_owner?'atendida':'pendiente'}</td></tr>`).join('')}
      </tbody></table>
    </div>
    <div class="card">
      <b>Reuniones</b>
      <table><thead><tr><th>Contacto</th><th>Inicio</th><th>Tema</th><th>Estado</th></tr></thead><tbody>
      ${(d.meetings||[]).map(x=>`<tr><td>${x.contact||''}</td><td>${x.start_iso||''}</td><td>${x.topic||''}</td><td>${x.status||''}</td></tr>`).join('')}
      </tbody></table>
    </div>
    <div class="card">
      <b>API</b>: <a href="/api/status">/api/status</a>
    </div>`;
}
load();
</script>
</body>
</html>"""


@app.get("/api/status")
def status():
    try:
        days = int((request.args.get("days") or "7").strip())
    except Exception:
        days = 7
    kind = (request.args.get("kind") or "all").strip() or "all"
    payload = _build_status(range_days=days, kind=kind)
    payload = _clean_for_cloud(payload)
    return jsonify(payload)


@app.post("/api/assistant/mode")
@app.post("/api/assistant/hours")
@app.post("/api/assistant/toggles")
@app.post("/api/urgencias/seen")
@app.post("/api/meetings/status")
@app.post("/api/services/action")
def readonly():
    return (
        jsonify(
            {
                "ok": False,
                "error": "readonly_cloud",
                "detail": "Este despliegue Vercel es solo lectura. Usa el panel local para controles.",
            }
        ),
        501,
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "clwabot-vercel-panel"})

