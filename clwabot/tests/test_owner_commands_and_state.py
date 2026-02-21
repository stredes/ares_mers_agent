import tempfile
import unittest
from pathlib import Path

from clwabot.core import state_store, whatsapp_agent


OWNER = "+56954764325"
OTHER = "+19999999999"


class OwnerCommandStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "state.json"
        self.orig_state_path = state_store.STATE_PATH
        state_store.STATE_PATH = self.state_path

    def tearDown(self):
        state_store.STATE_PATH = self.orig_state_path
        self.tmp.cleanup()

    def test_owner_pause_resume(self):
        r1 = whatsapp_agent.handle_incoming(OWNER, "/pausar")
        self.assertEqual(r1["policy"], "reply_to_vip")
        self.assertIn("pausado", r1["message"].lower())

        r2 = whatsapp_agent.handle_incoming(OTHER, "hola")
        self.assertEqual(r2["policy"], "silence")

        r3 = whatsapp_agent.handle_incoming(OWNER, "/reanudar")
        self.assertIn("reanudado", r3["message"].lower())
        r4 = whatsapp_agent.handle_incoming(OTHER, "tengo un error")
        self.assertEqual(r4["policy"], "reply_to_vip")

    def test_state_memory_updates(self):
        whatsapp_agent.handle_incoming(OTHER, "quiero soporte por error")
        st = state_store.load_state()
        self.assertIn(OTHER, st.get("contacts", {}))
        self.assertTrue(st["contacts"][OTHER]["last_messages"])


if __name__ == "__main__":
    unittest.main()
