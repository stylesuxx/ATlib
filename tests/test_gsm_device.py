import pytest

from atlib.errors import ATCommandError, CMEError
from atlib.GSM_Device import GSM_Device
from atlib.Status import Status

from fake_serial import at_response

AT_OK = at_response("AT")
SMS_HEADER = '+CMGL: 1,"REC UNREAD","+436601234567","","24/09/23,10:15:32+08"'


def gsm(make_device, *responses):
    """ A GSM_Device that answers the scripted responses after its constructor. """
    return make_device(GSM_Device, list(responses))


def sent(port) -> list[str]:
    """ Commands written after the constructor's ATE1, AT+CMEE=1 and AT. """
    return port.commands()[3:]


class TestGetSimStatus:
    def test_ready(self, make_device):
        device, port = gsm(make_device, AT_OK, at_response("AT+CPIN?", "+CPIN: READY"))

        assert device.get_sim_status() == Status.OK

    def test_puk_required(self, make_device):
        device, port = gsm(make_device, AT_OK, at_response("AT+CPIN?", "+CPIN: SIM PUK"))

        assert device.get_sim_status() == Status.ERROR_SIM_PUK

    def test_no_sim_inserted(self, make_device):
        """ A modem without a SIM answers AT+CPIN? with +CME ERROR: 10 and nothing else. """
        device, port = gsm(make_device, AT_OK, at_response("AT+CPIN?", status="+CME ERROR: 10"))

        assert device.get_sim_status() == Status.ERROR_SIM_NOT_INSERTED

    def test_other_answers_are_unknown(self, make_device):
        device, port = gsm(make_device, AT_OK, at_response("AT+CPIN?", status="+CME ERROR: 14"))

        assert device.get_sim_status() == Status.UNKNOWN


class TestUnlockSim:
    def test_already_unlocked_sends_no_pin(self, make_device):
        device, port = gsm(make_device, AT_OK, AT_OK, at_response("AT+CPIN?", "+CPIN: READY"))

        assert device.unlock_sim("1234") == Status.OK
        assert "AT+CPIN=1234" not in sent(port)

    def test_pin_is_sent_and_sms_ready_awaited(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            AT_OK,
            at_response("AT+CPIN?", "+CPIN: SIM PIN"),
            (at_response("AT+CPIN=1234"), "\r\nSMS Ready\r\n"),
        )

        assert device.unlock_sim("1234") == Status.OK
        assert sent(port)[-1] == "AT+CPIN=1234"
        assert device.await_urc("SMS Ready", timeout=0) is None

    def test_wrong_pin_returns_the_error(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            AT_OK,
            at_response("AT+CPIN?", "+CPIN: SIM PIN"),
            at_response("AT+CPIN=0000", status="+CME ERROR: 16"),
        )

        assert device.unlock_sim("0000") == "+CME ERROR: 16"


class TestPower:
    def test_reboot(self, make_device):
        device, port = gsm(make_device, at_response("AT+CFUN=1,1"))

        assert device.reboot() == Status.OK
        assert sent(port) == ["AT+CFUN=1,1"]

    def test_off(self, make_device):
        device, port = gsm(make_device, at_response("AT+CFUN=0"))

        assert device.off() == Status.OK

    def test_off_returns_after_ok_and_keeps_the_detach(self, make_device):
        device, port = gsm(make_device, (at_response("AT+CFUN=0"), "\r\n+CGEV: ME DETACH\r\n"))

        assert device.off() == Status.OK
        assert device.await_urc("DETACH", timeout=1) == "+CGEV: ME DETACH"

    def test_off_failure(self, make_device):
        device, port = gsm(make_device, at_response("AT+CFUN=0", status="ERROR"))

        assert device.off() == Status.ERROR


class TestSendSms:
    def test_text_mode_flow(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response("AT+CSMP=17,167,0,0"),
            at_response('AT+CMGS="+436601234567"', status="> "),
            "",
            "\r\n+CMGS: 5\r\n\r\nOK\r\n",
        )

        assert device.send_sms("+436601234567", "Hello") == Status.OK
        assert sent(port) == [
            "AT",
            'AT+CSCS="GSM"',
            "AT+CMGF=1",
            "AT+CSMP=17,167,0,0",
            'AT+CMGS="+436601234567"',
            "Hello",
            "\x1a",
        ]

    def test_flash_sms_sets_the_data_coding_scheme(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response("AT+CSMP=17,167,0,16"),
            at_response('AT+CMGS="+436601234567"', status="> "),
            "",
            "\r\n+CMGS: 6\r\n\r\nOK\r\n",
        )

        assert device.send_sms("+436601234567", "Hello", dcs=16) == Status.OK
        assert "AT+CSMP=17,167,0,16" in sent(port)

    def test_missing_prompt_aborts_before_the_body(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response("AT+CSMP=17,167,0,0"),
            at_response('AT+CMGS="+436601234567"', status="+CMS ERROR: 304"),
        )

        assert device.send_sms("+436601234567", "Hello") == "+CMS ERROR: 304"
        assert "Hello" not in sent(port)

    def test_failed_setup_step_returns_its_status(self, make_device):
        device, port = gsm(make_device, AT_OK, at_response('AT+CSCS="GSM"', status="ERROR"))

        assert device.send_sms("+436601234567", "Hello") == Status.ERROR
        assert sent(port) == ["AT", 'AT+CSCS="GSM"']


class TestReceiveSms:
    def test_one_unread_message(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response('AT+CMGL="REC UNREAD"', SMS_HEADER, "Hello world"),
        )

        assert device.receive_sms() == [["+436601234567", "24/09/23", "10:15:32", "Hello world"]]
        assert sent(port)[-1] == 'AT+CMGL="REC UNREAD"'

    def test_two_messages(self, make_device):
        second_header = '+CMGL: 2,"REC UNREAD","+436609876543","","24/09/23,11:00:00+08"'
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response('AT+CMGL="ALL"', SMS_HEADER, "First", second_header, "Second"),
        )

        assert device.receive_sms("ALL") == [
            ["+436601234567", "24/09/23", "10:15:32", "First"],
            ["+436609876543", "24/09/23", "11:00:00", "Second"],
        ]

    def test_multi_line_body_is_joined(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response('AT+CMGL="REC UNREAD"', SMS_HEADER, "First line", "Second line"),
        )

        assert device.receive_sms() == [["+436601234567", "24/09/23", "10:15:32", "First line\nSecond line"]]

    def test_negative_timezone_is_stripped(self, make_device):
        header = '+CMGL: 1,"REC UNREAD","+15551234567","","24/09/23,10:15:32-20"'
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response('AT+CMGL="REC UNREAD"', header, "Hello"),
        )

        assert device.receive_sms() == [["+15551234567", "24/09/23", "10:15:32", "Hello"]]

    def test_no_messages(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response('AT+CMGL="REC UNREAD"'),
        )

        assert device.receive_sms() == []

    def test_listing_failure_returns_the_status(self, make_device):
        device, port = gsm(
            make_device,
            AT_OK,
            at_response('AT+CSCS="GSM"'),
            at_response("AT+CMGF=1"),
            at_response('AT+CMGL="REC UNREAD"', status="+CMS ERROR: 313"),
        )

        assert device.receive_sms() == "+CMS ERROR: 313"


class TestDeleteReadSms:
    def test_sends_the_delete_flag(self, make_device):
        device, port = gsm(make_device, AT_OK, at_response("AT+CMGD=1,3"))

        assert device.delete_read_sms() == Status.OK
        assert sent(port) == ["AT", "AT+CMGD=1,3"]


class TestOperators:
    def test_current_operator(self, make_device):
        device, port = gsm(make_device, at_response("AT+COPS?", '+COPS: 0,0,"A1",7'))

        assert device.get_current_operator() == "A1"

    def test_no_current_operator(self, make_device):
        device, port = gsm(make_device, at_response("AT+COPS?", "+COPS: 0"))

        assert device.get_current_operator() is None

    def test_current_operator_error(self, make_device):
        device, port = gsm(make_device, at_response("AT+COPS?", status="ERROR"))

        with pytest.raises(ATCommandError):
            device.get_current_operator()

    def test_available_operators(self, make_device):
        listing = '+COPS: (2,"A1","A1","23201",7),(1,"Magenta","T-Mobile A","23203",7),,(0,1,2,3,4),(0,1,2)'
        device, port = gsm(make_device, at_response("AT+COPS=?", listing))

        operators = device.get_available_operators()

        assert [(o.stat, o.long, o.short, o.numeric, o.access_technologies) for o in operators] == [
            (2, "A1", "A1", 23201, 7),
            (1, "Magenta", "T-Mobile A", 23203, 7),
        ]

    def test_available_operators_without_access_technology(self, make_device):
        listing = '+COPS: (2,"A1","A1","23201"),,(0,1,2,3,4),(0,1,2)'
        device, port = gsm(make_device, at_response("AT+COPS=?", listing))

        operators = device.get_available_operators()

        assert [(o.numeric, o.access_technologies) for o in operators] == [(23201, None)]

    def test_set_operator(self, make_device):
        device, port = gsm(make_device, at_response('AT+COPS=1,1,"A1"'))

        assert device.set_operator("A1") == Status.OK
        assert sent(port) == ['AT+COPS=1,1,"A1"']

    def test_set_operator_auto(self, make_device):
        device, port = gsm(make_device, at_response("AT+COPS=0"))

        assert device.set_operator_auto() == Status.OK
        assert sent(port) == ["AT+COPS=0"]


class TestCalls:
    def test_call_with_caller_id(self, make_device):
        device, port = gsm(make_device, at_response("ATD+436601234567i;"))

        assert device.call("+436601234567") == Status.OK
        assert sent(port) == ["ATD+436601234567i;"]

    def test_call_without_caller_id(self, make_device):
        device, port = gsm(make_device, at_response("ATD+436601234567I;"))

        assert device.call("+436601234567", show_caller_id=False) == Status.OK
        assert sent(port) == ["ATD+436601234567I;"]

    def test_busy_line_returns_at_once(self, make_device):
        device, port = gsm(make_device, at_response("ATD+436601234567;", status="BUSY"))

        assert device.call("+436601234567") == Status.BUSY

    def test_wait_for_call_returns_on_ring(self, make_device):
        device, port = gsm(make_device)
        port.queue("\r\nRING\r\n")

        assert device.wait_for_call() is None
        assert device.await_urc("RING", timeout=0) is None

    def test_disconnect(self, make_device):
        device, port = gsm(make_device, at_response("AT+CHUP"))

        assert device.disconnect() == Status.OK
        assert sent(port) == ["AT+CHUP"]

    def test_accept_call(self, make_device):
        device, port = gsm(make_device, at_response("ATA"))

        assert device.accept_call() == Status.OK
        assert sent(port) == ["ATA"]


class TestSignal:
    def test_rssi_and_ber(self, make_device):
        device, port = gsm(make_device, at_response("AT+CSQ", "+CSQ: 20,0"))

        assert device.get_signal() == (20, 0)

    def test_unknown_signal(self, make_device):
        device, port = gsm(make_device, at_response("AT+CSQ", "+CSQ: 99,99"))

        assert device.get_signal() == (99, 99)

    def test_error_answer(self, make_device):
        device, port = gsm(make_device, at_response("AT+CSQ", status="ERROR"))

        with pytest.raises(ATCommandError):
            device.get_signal()

    def test_cme_answer(self, make_device):
        device, port = gsm(make_device, at_response("AT+CSQ", status="+CME ERROR: 10"))

        with pytest.raises(CMEError):
            device.get_signal()


class TestIdentity:
    def test_manufacturer_with_prefix(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGMI", "+CGMI: SIMCOM"))

        assert device.get_manufacturer() == "SIMCOM"

    def test_manufacturer_bare(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGMI", "SIMCOM INCORPORATED"))

        assert device.get_manufacturer() == "SIMCOM INCORPORATED"

    def test_model_with_prefix(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGMM", "+CGMM: SIM7600G-H"))

        assert device.get_model() == "SIM7600G-H"

    def test_model_bare(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGMM", "SIMCOM_SIM7600G-H"))

        assert device.get_model() == "SIMCOM_SIM7600G-H"

    def test_serial(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGSN", "861234567890123"))

        assert device.get_serial() == "861234567890123"

    def test_imei(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGSN", "861234567890123"))

        assert device.get_imei() == "861234567890123"

    def test_imsi(self, make_device):
        device, port = gsm(make_device, at_response("AT+CIMI", "232010123456789"))

        assert device.get_imsi() == "232010123456789"

    def test_iccid(self, make_device):
        device, port = gsm(make_device, at_response("AT+ICCID", "+ICCID: 8943010012345678901"))

        assert device.get_iccid() == "8943010012345678901"


class TestNetwork:
    def test_gprs_status(self, make_device):
        device, port = gsm(make_device, at_response("AT+CGATT?", "+CGATT: 1"))

        assert device.get_gprs_status() == "1"

    def test_enable_location_reporting(self, make_device):
        device, port = gsm(make_device, at_response("AT+CREG=2"))

        assert device.enable_location_reporting() == Status.OK
        assert sent(port) == ["AT+CREG=2"]

    def test_network_registration(self, make_device):
        device, port = gsm(make_device, at_response("AT+CREG?", "+CREG: 0,1"))

        assert device.get_network_registration() == (0, 1)

    def test_network_registration_with_location(self, make_device):
        device, port = gsm(make_device, at_response("AT+CREG?", '+CREG: 2,1,"1A2B","01C3D4E5"'))

        assert device.get_network_registration() == (2, 1)

    def test_cell_location(self, make_device):
        device, port = gsm(make_device, at_response("AT+CREG?", '+CREG: 2,1,"1A2B","01C3D4E5"'))

        assert device.get_cell_location() == (2, 1, 0x1A2B, 0x01C3D4E5)

    def test_cell_location_error(self, make_device):
        device, port = gsm(make_device, at_response("AT+CREG?", status="ERROR"))

        with pytest.raises(ATCommandError):
            device.get_cell_location()
