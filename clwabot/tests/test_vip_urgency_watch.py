import unittest

from clwabot.core.urgencia_handler import mensaje_contiene_urgencia
from clwabot.hooks.vip_urgency_watch import extract_vip_message, should_dispatch


class VipUrgencyWatchTests(unittest.TestCase):
    def test_extract_vip_message_from_structured_json(self):
        line = (
            '{"0":"{\\"module\\":\\"web-inbound\\"}",'
            '"1":{"from":"+56975551112","to":"+56922222222","body":"amor, emergencia ahora"},'
            '"2":"inbound message"}'
        )
        msg = extract_vip_message(line)
        self.assertEqual(msg, "amor, emergencia ahora")

    def test_ignore_non_vip_structured_json(self):
        line = (
            '{"0":"{\\"module\\":\\"web-inbound\\"}",'
            '"1":{"from":"+56911111111","to":"+56922222222","body":"urgencia"},'
            '"2":"inbound message"}'
        )
        msg = extract_vip_message(line)
        self.assertIsNone(msg)

    def test_dispatch_for_synonym_keyword(self):
        line = '[whatsapp] inbound message from +56975551112: "amor, emergencia con el auto"'
        msg = should_dispatch(line, session_active=False)
        self.assertEqual(msg, "amor, emergencia con el auto")

    def test_do_not_dispatch_without_keyword_or_session(self):
        line = '[whatsapp] inbound message from +56975551112: "hola como estas"'
        msg = should_dispatch(line, session_active=False)
        self.assertIsNone(msg)

    def test_dispatch_when_session_is_active(self):
        line = '[whatsapp] inbound message from +56975551112: "te mando detalle"'
        msg = should_dispatch(line, session_active=True)
        self.assertEqual(msg, "te mando detalle")


class UrgencyKeywordTests(unittest.TestCase):
    def test_detect_multiple_urgency_variants(self):
        self.assertTrue(mensaje_contiene_urgencia("esto es urgente"))
        self.assertTrue(mensaje_contiene_urgencia("tengo una emergencia"))
        self.assertTrue(mensaje_contiene_urgencia("es crítico, ayuda ahora"))
        self.assertTrue(mensaje_contiene_urgencia("auxilio por favor"))

    def test_ignore_non_urgency_text(self):
        self.assertFalse(mensaje_contiene_urgencia("te escribo luego para coordinar"))


if __name__ == "__main__":
    unittest.main()
