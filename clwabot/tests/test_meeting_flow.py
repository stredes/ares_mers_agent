import tempfile
import unittest
from pathlib import Path

from clwabot.core import ics_maker, meeting_session, whatsapp_agent


CONTACT = "+11111111111"


class MeetingFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.sessions_path = self.base / "meeting_sessions.json"
        self.calendar_dir = self.base / "calendar"
        self.calendar_dir.mkdir(parents=True, exist_ok=True)

        self.orig_sessions = meeting_session.SESSIONS_PATH
        self.orig_cal = ics_maker.CAL_DIR
        meeting_session.SESSIONS_PATH = self.sessions_path
        ics_maker.CAL_DIR = self.calendar_dir

    def tearDown(self):
        meeting_session.SESSIONS_PATH = self.orig_sessions
        ics_maker.CAL_DIR = self.orig_cal
        self.tmp.cleanup()

    def _send(self, text: str):
        return whatsapp_agent.handle_incoming(CONTACT, text)

    def test_meeting_trigger_and_form(self):
        start = self._send("hola, quiero agendar una reunion")
        self.assertEqual(start["policy"], "reply_to_vip")
        self.assertIn("asistente", start["message"].lower())
        self.assertIn("tema", start["message"].lower())

        self._send("Demo comercial")
        self._send("lunes")
        self._send("10:30")
        self._send("1 hora")
        confirm = self._send("videollamada")
        self.assertIn("confirmar", confirm["message"].lower())

        done = self._send("1")
        self.assertTrue(done["vip_ics_path"])
        self.assertTrue(Path(done["vip_ics_path"]).exists())
        self.assertIn("reunión", done["owner_message"].lower())


if __name__ == "__main__":
    unittest.main()
