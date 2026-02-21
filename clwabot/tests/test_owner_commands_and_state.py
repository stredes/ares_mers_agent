import tempfile
import unittest
from pathlib import Path

from clwabot.core import oscp_agent, state_store, whatsapp_agent


OWNER = "+56954764325"
OTHER = "+19999999999"


class OwnerCommandStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "state.json"
        self.oscp_path = Path(self.tmp.name) / "oscp.yaml"
        self.orig_state_path = state_store.STATE_PATH
        self.orig_oscp_path = oscp_agent.CONFIG_OSCP
        state_store.STATE_PATH = self.state_path
        oscp_agent.CONFIG_OSCP = self.oscp_path
        self.oscp_path.write_text(
            (
                "profile:\n"
                "  name: test\n"
                "  enrolled: true\n"
                "  hours_per_week: 8\n"
                "platforms: []\n"
                "weak_spots: [\"Windows privesc\"]\n"
                "labs:\n"
                "  - name: LabAlpha\n"
                "    platform: HTB\n"
                "    ip: 10.10.10.10\n"
                "    status: pending\n"
                "    notes: []\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        state_store.STATE_PATH = self.orig_state_path
        oscp_agent.CONFIG_OSCP = self.orig_oscp_path
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

    def test_oscp_owner_commands(self):
        status = whatsapp_agent.handle_incoming(OWNER, "/oscp-status")
        self.assertEqual(status["policy"], "reply_to_vip")
        self.assertIn("oscp status", status["message"].lower())

        plan = whatsapp_agent.handle_incoming(OWNER, "/oscp-plan")
        self.assertIn("plan semanal", plan["message"].lower())

        upd = whatsapp_agent.handle_incoming(OWNER, "/oscp-lab LabAlpha in_progress")
        self.assertIn("actualizado", upd["message"].lower())

        note = whatsapp_agent.handle_incoming(OWNER, "/oscp-note LabAlpha | revisar smb y winpeas")
        self.assertIn("nota agregada", note["message"].lower())

        cfg = oscp_agent.load_config()
        self.assertEqual(cfg["labs"][0]["status"], "in_progress")
        self.assertTrue(cfg["labs"][0]["notes"])


if __name__ == "__main__":
    unittest.main()
