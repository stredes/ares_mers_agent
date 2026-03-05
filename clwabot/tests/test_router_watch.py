import unittest

from clwabot.hooks.whatsapp_router_watch import _is_plain_metadata_only, parse_inbound_line


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

    def test_parse_structured_web_inbound(self):
        line = (
            '{"0":"{\\"module\\":\\"web-inbound\\"}",'
            '"1":{"from":"+56911111111","to":"+56922222222","body":"hola test"},'
            '"2":"inbound message"}'
        )
        msg = parse_inbound_line(line)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertEqual(msg.msisdn, "+56911111111")
        self.assertEqual(msg.text, "hola test")

    def test_parse_structured_wrapped_body(self):
        line = (
            '{"0":"{\\"module\\":\\"web-auto-reply\\"}",'
            '"1":{"from":"+56911111111","to":"+56922222222","body":"[WhatsApp +56911111111] hola mundo"},'
            '"2":"inbound web message"}'
        )
        msg = parse_inbound_line(line)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertEqual(msg.msisdn, "+56911111111")
        self.assertEqual(msg.text, "hola mundo")

    def test_detect_plain_metadata_line(self):
        text = "2026-02-22T14:20:21.952Z [whatsapp] Inbound message +56975551112 -> +56954764325 (direct, text, 8 chars)"
        self.assertTrue(_is_plain_metadata_only(text))


if __name__ == "__main__":
    unittest.main()
