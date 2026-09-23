import pytest

from atlib.AT_Device import AT_Device
from atlib.Response import Response
from atlib.Status import Status
from atlib.errors import ATCommandError, ATError, ATParseError, ATTimeout, CMEError, CMSError
from fake_serial import at_response


class TestStatus:
    def test_ok(self):
        response = Response(["AT+CSQ", "+CSQ: 20,0", "OK"], "AT+CSQ")

        assert response.status == Status.OK
        assert response.final == "OK"
        assert response.error is None
        assert response.is_ok

    def test_error(self):
        response = Response(["AT+FOO", "ERROR"], "AT+FOO")

        assert response.status == Status.ERROR
        assert isinstance(response.error, ATCommandError)
        assert not response.is_ok

    def test_prompt(self):
        response = Response(['AT+CMGS="123"', "> "], 'AT+CMGS="123"')

        assert response.status == Status.PROMPT
        assert response.error is None

    def test_timeout(self):
        response = Response(["AT+CSQ\r\r\n", Status.TIMEOUT], "AT+CSQ")

        assert response.status == Status.TIMEOUT
        assert isinstance(response.error, ATTimeout)

    def test_numeric_cme_error(self):
        response = Response(["AT+CPIN?", "+CME ERROR: 10"], "AT+CPIN?")

        assert response.status == Status.ERROR
        assert response.final == "+CME ERROR: 10"
        assert isinstance(response.error, CMEError)
        assert response.error.code == 10
        assert response.error.message == ""

    def test_verbose_cme_error(self):
        response = Response(["AT+CPIN?", "+CME ERROR: SIM not inserted"], "AT+CPIN?")

        assert isinstance(response.error, CMEError)
        assert response.error.code is None
        assert response.error.message == "SIM not inserted"

    def test_cms_error(self):
        response = Response(['AT+CMGS="123"', "+CMS ERROR: 304"], 'AT+CMGS="123"')

        assert isinstance(response.error, CMSError)
        assert response.error.code == 304

    def test_no_final_result_code(self):
        response = Response(["AT+CFUN=0", "+CGEV: ME DETACH"], "AT+CFUN=0")

        assert response.status == Status.UNKNOWN
        assert isinstance(response.error, ATError)

    def test_urc_after_the_final_result_code_is_kept_as_a_line(self):
        response = Response(["AT+CFUN=0", "OK", "+CGEV: ME DETACH"], "AT+CFUN=0")

        assert response.status == Status.OK
        assert response.lines == ["+CGEV: ME DETACH"]


class TestLines:
    def test_echo_is_separated_from_lines(self):
        response = Response(["AT+CSQ", "+CSQ: 20,0", "OK"], "AT+CSQ")

        assert response.echo == "AT+CSQ"
        assert response.lines == ["+CSQ: 20,0"]

    def test_missing_echo_leaves_the_first_line_in_place(self):
        response = Response(["SIMCOM_Ltd", "OK"], "AT+CGMI")

        assert response.echo is None
        assert response.lines == ["SIMCOM_Ltd"]

    def test_line_by_prefix_skips_a_urc(self):
        response = Response(["AT+CSQ", "+CREG: 1", "+CSQ: 20,0", "OK"], "AT+CSQ")

        assert response.line("+CSQ") == "+CSQ: 20,0"

    def test_line_without_prefix_is_the_first_line(self):
        response = Response(["AT+CGSN", "861234567890123", "OK"], "AT+CGSN")

        assert response.line() == "861234567890123"

    def test_missing_line_raises(self):
        response = Response(["AT+CSQ", "OK"], "AT+CSQ")

        with pytest.raises(ATParseError):
            response.line("+CSQ")


class TestValue:
    def test_payload_after_the_prefix(self):
        response = Response(["AT+CGATT?", "+CGATT: 1", "OK"], "AT+CGATT?")

        assert response.value("+CGATT") == "1"

    def test_surrounding_quotes_are_removed(self):
        response = Response(["AT+ICCID", '+ICCID: "8943010012345678901"', "OK"], "AT+ICCID")

        assert response.value("+ICCID") == "8943010012345678901"

    def test_bare_answer_falls_back_to_the_first_line(self):
        response = Response(["AT+CGMI", "SIMCOM INCORPORATED", "OK"], "AT+CGMI")

        assert response.value("+CGMI") == "SIMCOM INCORPORATED"

    def test_only_the_first_colon_splits(self):
        response = Response(["AT+CCED=0,1", "+CCED:LTE current cell info:232,1", "OK"], "AT+CCED=0,1")

        assert response.value("+CCED") == "LTE current cell info:232,1"


class TestFields:
    def test_plain_fields(self):
        response = Response(["AT+CSQ", "+CSQ: 20,0", "OK"], "AT+CSQ")

        assert response.fields("+CSQ") == ["20", "0"]

    def test_quoted_fields_keep_their_commas(self):
        response = Response(["AT+COPS?", '+COPS: 0,0,"A1, Austria",7', "OK"], "AT+COPS?")

        assert response.fields("+COPS") == ["0", "0", "A1, Austria", "7"]

    def test_empty_fields_survive(self):
        response = Response(["AT+CGDCONT?", '+CGDCONT: 2,"IPV4V6","","",0', "OK"], "AT+CGDCONT?")

        assert response.fields("+CGDCONT") == ["2", "IPV4V6", "", "", "0"]

    def test_spaces_after_commas_are_dropped(self):
        response = Response(["AT*BANDIND?", "*BANDIND: 0, 3, 7", "OK"], "AT*BANDIND?")

        assert response.fields("*BANDIND") == ["0", "3", "7"]

    def test_rows_return_one_list_per_matching_line(self):
        response = Response(["AT+CGPADDR", '+CGPADDR: 1,"10.0.0.1"', "+CGPADDR: 2", "OK"], "AT+CGPADDR")

        assert response.rows("+CGPADDR") == [["1", "10.0.0.1"], ["2"]]

    def test_rows_without_matching_lines_are_empty(self):
        response = Response(["AT+CGPADDR", "OK"], "AT+CGPADDR")

        assert response.rows("+CGPADDR") == []


class TestRaiseForStatus:
    def test_ok_returns_the_response(self):
        response = Response(["AT", "OK"], "AT")

        assert response.raise_for_status() is response

    def test_error_raises_with_the_response_attached(self):
        response = Response(["AT+FOO", "ERROR"], "AT+FOO")

        with pytest.raises(ATCommandError) as info:
            response.raise_for_status()
        assert info.value.response is response

    def test_cme_error_raises_with_code(self):
        response = Response(["AT+CPIN?", "+CME ERROR: 10"], "AT+CPIN?")

        with pytest.raises(CMEError) as info:
            response.raise_for_status()
        assert info.value.code == 10

    def test_timeout_raises(self):
        response = Response(["", Status.TIMEOUT], "AT")

        with pytest.raises(ATTimeout):
            response.raise_for_status()


class TestCommand:
    def test_writes_and_parses(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT+CSQ", "+CSQ: 20,0")])

        response = device.command("AT+CSQ")

        assert port.commands()[-1] == "AT+CSQ"
        assert response.fields("+CSQ") == ["20", "0"]

    def test_stopterm_is_passed_through(self, make_device):
        device, port = make_device(AT_Device, ["AT+CFUN=0\r\r\nOK\r\n\r\n+CGEV: ME DETACH\r\n"])

        response = device.command("AT+CFUN=0", stopterm="DETACH")

        assert response.is_ok
        assert response.lines == ["+CGEV: ME DETACH"]

    def test_timeout_becomes_a_response(self, make_device):
        device, port = make_device(AT_Device, [""])

        response = device.command("AT+CSQ", timeout=0.05)

        assert response.status == Status.TIMEOUT
