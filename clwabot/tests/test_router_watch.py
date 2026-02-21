import unittest

from clwabot.hooks.whatsapp_router_watch import parse_inbound_line


class RouterWatchTests(unittest.TestCase):
    def test_parse_inbound_with_from_and_quotes(self):
        line = '[whatsapp] inbound message from +56911111111: "Hola, quiero agendar reunion"'
        msg = parse_inbound_line(line)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertEqual(msg.msisdn, "+56911111111")
        self.assertIn("agendar", msg.text.lower())

    def test_ignore_non_inbound(self):
        line = '[whatsapp] outbound message to +56911111111: "ok"'
        msg = parse_inbound_line(line)
        self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
