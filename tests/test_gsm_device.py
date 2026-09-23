import pytest

from atlib.GSM_Device import GSM_Device
from atlib.Status import Status

from fake_serial import at_response


def sim_status_for(make_device, response: str) -> str:
    """ Run get_sim_status against one scripted AT+CPIN? response. """
    # get_sim_status calls reset_state first, which sends a bare AT.
    device, port = make_device(GSM_Device, [at_response("AT"), response])
    return device.get_sim_status()


class TestGetSimStatus:
    def test_ready(self, make_device):
        assert sim_status_for(make_device, at_response("AT+CPIN?", "+CPIN: READY")) == Status.OK

    def test_puk_required(self, make_device):
        assert sim_status_for(make_device, at_response("AT+CPIN?", "+CPIN: SIM PUK")) == Status.ERROR_SIM_PUK

    def test_no_sim_inserted(self, make_device):
        """ A modem without a SIM answers AT+CPIN? with +CME ERROR: 10 and nothing else. """
        response = at_response("AT+CPIN?", status="+CME ERROR: 10")
        assert sim_status_for(make_device, response) == Status.ERROR_SIM_NOT_INSERTED

    def test_other_answers_are_unknown(self, make_device):
        response = at_response("AT+CPIN?", status="+CME ERROR: 14")
        assert sim_status_for(make_device, response) == Status.UNKNOWN
