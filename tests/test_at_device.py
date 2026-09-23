import unittest

from atlib.AT_Device import AT_Device


class TestHasTerminator(unittest.TestCase):
    def test_ok_terminates(self):
        self.assertTrue(AT_Device.has_terminator("AT+CPIN?\r\n+CPIN: READY\r\n\r\nOK\r\n"))

    def test_error_terminates(self):
        self.assertTrue(AT_Device.has_terminator("AT+FOO\r\n\r\nERROR\r\n"))

    def test_prompt_terminates(self):
        self.assertTrue(AT_Device.has_terminator("AT+CMGS=\"123\"\r\n> "))

    def test_cme_error_terminates(self):
        """A modem without a SIM answers AT+CPIN? with +CME ERROR: 10 and nothing else."""
        self.assertTrue(AT_Device.has_terminator("AT+CPIN?\r\n+CME ERROR: 10\r\n"))

    def test_cms_error_terminates(self):
        self.assertTrue(AT_Device.has_terminator("AT+CMGS=\"123\"\r\n+CMS ERROR: 500\r\n"))

    def test_partial_cme_error_line_keeps_reading(self):
        self.assertFalse(AT_Device.has_terminator("AT+CPIN?\r\n+CME ERROR: 1"))

    def test_intermediate_lines_keep_reading(self):
        self.assertFalse(AT_Device.has_terminator("AT+CPIN?\r\n+CPIN: READY\r\n"))

    def test_stopterm_terminates(self):
        self.assertTrue(AT_Device.has_terminator("AT+CMGL\r\n+CMGL: 1", stopterm="+CMGL"))


class TestTokenizeResponse(unittest.TestCase):
    def test_cme_error_is_kept_after_the_echo(self):
        tokens = AT_Device.tokenize_response("AT+CPIN?\r\n+CME ERROR: 10\r\n")

        self.assertEqual(tokens, ["AT+CPIN?", "+CME ERROR: 10"])
