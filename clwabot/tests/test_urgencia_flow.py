import json
import tempfile
import unittest
from pathlib import Path

from clwabot.core import ics_maker, urgencia_handler, urgencia_session, whatsapp_agent


VIP = "+56975551112"


class UrgenciaFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

        self.urgencias_path = self.base / "urgencias.json"
        self.sessions_path = self.base / "urgencia_sessions.json"
        self.calendar_dir = self.base / "calendar"
        self.calendar_dir.mkdir(parents=True, exist_ok=True)

        self._orig = {
            "uh_data": urgencia_handler.DATA_PATH,
            "us_sessions": urgencia_session.SESSIONS_PATH,
            "im_cal": ics_maker.CAL_DIR,
            "uh_cal": urgencia_handler.CALENDAR_DIR,
        }

        urgencia_handler.DATA_PATH = self.urgencias_path
        urgencia_handler.CALENDAR_DIR = self.calendar_dir
        urgencia_session.SESSIONS_PATH = self.sessions_path
        ics_maker.CAL_DIR = self.calendar_dir

    def tearDown(self):
        urgencia_handler.DATA_PATH = self._orig["uh_data"]
        urgencia_handler.CALENDAR_DIR = self._orig["uh_cal"]
        urgencia_session.SESSIONS_PATH = self._orig["us_sessions"]
        ics_maker.CAL_DIR = self._orig["im_cal"]
        self.tmp.cleanup()

    def _send(self, text: str):
        return whatsapp_agent.handle_incoming(VIP, text)

    def test_nota_flow_with_confirmation(self):
        self._send("urgencia")
        self._send("2")
        confirm = self._send("Necesito que Lucas me llame ahora")
        self.assertIn("Responde", confirm["message"])
        done = self._send("1")
        self.assertEqual(done["policy"], "reply_to_vip")
        self.assertIn("registrado", done["message"].lower())
        self.assertTrue(done["owner_message"])

    def test_recordatorio_generates_ics(self):
        self._send("urgente")
        self._send("3")
        self._send("Pagar cuenta mañana 19:30")
        done = self._send("confirmar")
        self.assertTrue(done["vip_ics_path"])
        self.assertTrue(Path(done["vip_ics_path"]).exists())
        self.assertIn("recordatorio", done["owner_message"].lower())

    def test_event_flow_with_config(self):
        self._send("urgencia")
        self._send("1")
        self._send("Reunion banco, lunes 10:00")
        step = self._send("si")
        self.assertIn("configurar", step["message"].lower())
        done = self._send("2")
        self.assertTrue(done["vip_ics_path"])
        self.assertTrue(Path(done["vip_ics_path"]).exists())

    def test_cancel_session(self):
        self._send("urgencia")
        self._send("2")
        cancelled = self._send("cancelar")
        self.assertIn("cerre", cancelled["message"].lower().replace("é", "e"))
        self.assertFalse(cancelled["owner_message"])

    def test_dedup_window(self):
        first = urgencia_handler.registrar_urgencia(
            from_msisdn=VIP,
            text="mismo mensaje",
            kind="nota",
        )
        second = urgencia_handler.registrar_urgencia(
            from_msisdn=VIP,
            text="mismo mensaje",
            kind="nota",
        )
        self.assertEqual(first.id, second.id)
        self.assertTrue(second.is_duplicate)
        state = json.loads(self.urgencias_path.read_text(encoding="utf-8"))
        self.assertEqual(len(state.get("urgencias", [])), 1)

    def test_immediate_escalation_retry_payload(self):
        self._send("urgencia")
        self._send("4")
        self._send("Hay una emergencia real en casa")
        done = self._send("1")
        self.assertTrue(done.get("owner_retry_message"))
        self.assertGreater(int(done.get("owner_retry_delay_sec", "0")), 0)


if __name__ == "__main__":
    unittest.main()
