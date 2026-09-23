import pytest

from atlib.AT_Device import AT_Device
from atlib.Status import Status

from fake_serial import at_response


class TestHasTerminator:
    def test_ok_terminates(self):
        assert AT_Device.has_terminator("AT+CPIN?\r\n+CPIN: READY\r\n\r\nOK\r\n")

    def test_error_terminates(self):
        assert AT_Device.has_terminator("AT+FOO\r\n\r\nERROR\r\n")

    def test_prompt_terminates(self):
        assert AT_Device.has_terminator("AT+CMGS=\"123\"\r\n> ")

    def test_cme_error_terminates(self):
        """ A modem without a SIM answers AT+CPIN? with +CME ERROR: 10 and nothing else. """
        assert AT_Device.has_terminator("AT+CPIN?\r\n+CME ERROR: 10\r\n")

    def test_cms_error_terminates(self):
        assert AT_Device.has_terminator("AT+CMGS=\"123\"\r\n+CMS ERROR: 500\r\n")

    def test_verbose_cme_error_terminates(self):
        """ With AT+CMEE=2 the error carries text instead of a number. """
        assert AT_Device.has_terminator("AT+CPIN?\r\n+CME ERROR: SIM not inserted\r\n")

    def test_partial_cme_error_line_keeps_reading(self):
        assert not AT_Device.has_terminator("AT+CPIN?\r\n+CME ERROR: 1")

    def test_intermediate_lines_keep_reading(self):
        assert not AT_Device.has_terminator("AT+CPIN?\r\n+CPIN: READY\r\n")

    def test_ok_inside_a_line_keeps_reading(self):
        assert not AT_Device.has_terminator("AT+CMGL\r\n+CMGL: 1\r\nOK see you\r\n")

    def test_stopterm_terminates(self):
        assert AT_Device.has_terminator("AT+CMGL\r\n+CMGL: 1", stopterm="+CMGL")

    @pytest.mark.parametrize("final", ["NO CARRIER", "BUSY", "NO ANSWER", "NO DIALTONE"])
    def test_call_result_codes_terminate(self, final):
        """ ATD ends with one of the V.250 call result codes instead of OK. """
        assert AT_Device.has_terminator(f"ATD+436601234567;\r\r\n{final}\r\n")


class TestTokenizeResponse:
    def test_echo_lines_and_status(self):
        tokens = AT_Device.tokenize_response("AT+CSQ\r\r\n+CSQ: 20,0\r\n\r\nOK\r\n")

        assert tokens == ["AT+CSQ", "+CSQ: 20,0", "OK"]

    def test_urc_before_the_echo_is_dropped(self):
        tokens = AT_Device.tokenize_response("\r\n+CREG: 1\r\nAT+CSQ\r\r\n+CSQ: 20,0\r\n\r\nOK\r\n")

        assert tokens == ["AT+CSQ", "+CSQ: 20,0", "OK"]

    def test_lines_after_the_echo_are_kept(self):
        tokens = AT_Device.tokenize_response("AT+CMGL\r\r\n+CMGL: 1,\"REC READ\"\r\nHello\r\n\r\nOK\r\n")

        assert tokens == ["AT+CMGL", "+CMGL: 1,\"REC READ\"", "Hello", "OK"]

    def test_cme_error_is_kept_after_the_echo(self):
        tokens = AT_Device.tokenize_response("AT+CPIN?\r\n+CME ERROR: 10\r\n")

        assert tokens == ["AT+CPIN?", "+CME ERROR: 10"]

    def test_prompt_is_a_token(self):
        assert AT_Device.tokenize_response("AT+CMGS=\"123\"\r\r\n> ") == ["AT+CMGS=\"123\"", "> "]


class TestHelpersOnInstance:
    def test_has_terminator(self, make_device):
        device, port = make_device(AT_Device)

        assert device.has_terminator("AT\r\r\nOK\r\n")

    def test_tokenize_response(self, make_device):
        device, port = make_device(AT_Device)

        assert device.tokenize_response("AT\r\r\nOK\r\n") == ["AT", "OK"]


class TestRead:
    def test_verbose_error_ends_the_response(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+CPIN?", status="+CME ERROR: 10")])

        device.write("AT+CPIN?")

        assert device.read() == ["AT+CPIN?", "+CME ERROR: 10"]

    def test_prompt_ends_the_response(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+CMGS=\"123\"", status="> ")])

        device.write("AT+CMGS=\"123\"")

        assert device.read() == ["AT+CMGS=\"123\"", "> "]

    def test_call_result_code_ends_the_response(self, make_device):
        device, port = make_device(AT_Device, [at_response("ATD+436601234567;", status="BUSY")])

        device.write("ATD+436601234567;")

        assert device.read() == ["ATD+436601234567;", "BUSY"]

    def test_stopterm_ends_the_response_early(self, make_device):
        device, port = make_device(AT_Device, ["AT+CFUN=0\r\r\nOK\r\n\r\n+CGEV: ME DETACH\r\n"])

        device.write("AT+CFUN=0")

        assert device.read(stopterm="DETACH") == ["AT+CFUN=0", "OK", "+CGEV: ME DETACH"]

    def test_second_burst_is_left_for_the_next_read(self, make_device):
        device, port = make_device(AT_Device, [(at_response("AT+CPIN=1234"), "\r\nSMS Ready\r\n")])

        device.write("AT+CPIN=1234")

        assert device.read() == ["AT+CPIN=1234", "OK"]
        assert device.read(stopterm="SMS Ready") == ["SMS Ready"]

    def test_multibyte_character_split_across_chunks(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+CMGL", "Grüße")], chunk_size=1)

        device.write("AT+CMGL")

        assert device.read() == ["AT+CMGL", "Grüße", "OK"]

    def test_invalid_bytes_return_the_text_so_far_with_error(self, make_device):
        device, port = make_device(AT_Device, [""], chunk_size=1)

        device.write("AT+CMGL")
        port.bursts.append(b"AT+CMGL\r\r\n\xff\xfe\r\n\r\nOK\r\n")

        assert device.read() == ["AT+CMGL\r\r\n", Status.ERROR]


class TestReadStatus:
    def test_ok(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT")])

        device.write("AT")

        assert device.read_status() == Status.OK

    def test_error(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+FOO", status="ERROR")])

        device.write("AT+FOO")

        assert device.read_status() == Status.ERROR

    def test_prompt(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+CMGS=\"123\"", status="> ")])

        device.write("AT+CMGS=\"123\"")

        assert device.read_status() == Status.PROMPT

    def test_timeout_argument_bounds_the_wait(self, make_device):
        device, port = make_device(AT_Device, [""])

        device.write("AT+COPS=1,1,\"A1\"")

        assert device.read_status(timeout=0.05) == Status.TIMEOUT

    def test_verbose_error_is_returned_as_is(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+CPIN?", status="+CME ERROR: 10")])

        device.write("AT+CPIN?")

        assert device.read_status() == "+CME ERROR: 10"


class TestSyncBaudrate:
    def test_ok_on_first_try(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT")])

        assert device.sync_baudrate() == Status.OK
        assert port.commands() == ["ATE1", "AT+CMEE=1", "AT"]

    def test_without_retry_gives_up_after_one_failure(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT", status="ERROR")])

        assert device.sync_baudrate(retry=False) == Status.ERROR
        assert port.commands() == ["ATE1", "AT+CMEE=1", "AT"]


class TestResetState:
    def test_drains_pending_input_and_retries_until_ok(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT", status="ERROR"), at_response("AT")])
        port.queue("+CREG: 1\r\n")

        device.reset_state()

        assert port.commands() == ["ATE1", "AT+CMEE=1", "AT", "AT"]
