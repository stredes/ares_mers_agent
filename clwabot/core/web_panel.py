#!/usr/bin/env python3
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .meeting_session import get_active_meeting_session
from .state_store import load_state
from .urgencia_session import get_active_session


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path not in {"/", "/status.json"}:
            self.send_response(404)
            self.end_headers()
            return

        state = load_state()
        contacts = state.get("contacts", {})
        payload = {
            "assistant": state.get("assistant", {}),
            "contacts_total": len(contacts),
            "contacts": contacts,
            "active_urgencias": [msisdn for msisdn in contacts if get_active_session(msisdn)],
            "active_meetings": [msisdn for msisdn in contacts if get_active_meeting_session(msisdn)],
            "metrics_count": len(state.get("metrics", {}).get("events", [])),
        }

        if self.path == "/status.json":
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>clwabot panel</title></head>
<body style="font-family: sans-serif; margin: 20px;">
<h2>clwabot panel</h2>
<p>assistant mode: <b>{payload['assistant'].get('mode', 'normal')}</b> | paused: <b>{payload['assistant'].get('paused', False)}</b></p>
<p>contacts: <b>{payload['contacts_total']}</b> | metrics: <b>{payload['metrics_count']}</b></p>
<p>active urgencias: <b>{len(payload['active_urgencias'])}</b> | active meetings: <b>{len(payload['active_meetings'])}</b></p>
<p><a href="/status.json">status.json</a></p>
</body></html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    server = HTTPServer(("127.0.0.1", 8787), Handler)
    print("clwabot web panel listening on http://127.0.0.1:8787")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
