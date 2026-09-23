import pytest

from atlib.errors import ATCommandError
from atlib.SIM7600GH import SIM7600GH

from fake_serial import at_response

CNBP = "+CNBP: 0x100200000EE80380,0x480000000000000000000000000000000000000000000042000007FFFFDF3FFF,0x000000000000003F"
CPSI = "+CPSI: LTE,Online,232-01,0x7C11,12345678,456,EUTRAN-BAND3,1850,5,5,-98,-10,-65,15"


def sim7600(make_device, *responses):
    return make_device(SIM7600GH, list(responses))


def sent(port) -> list[str]:
    return port.commands()[2:]


class TestBands:
    def test_allowed_bands_from_lte_bitmask(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CNBP?", CNBP))

        assert device.get_allowed_bands() == [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21,
            23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
            40, 41, 42, 43, 66, 71,
        ]

    def test_allowed_bands_error(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CNBP?", status="ERROR"))

        with pytest.raises(ATCommandError):
            device.get_allowed_bands()

    def test_active_band(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CPSI?", CPSI))

        assert device.get_active_band() == 3

    def test_active_band_when_offline(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CPSI?", "+CPSI: NO SERVICE,Online"))

        assert device.get_active_band() == 0


class TestVersion:
    def test_firmware_version(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CGMR", "+CGMR: LE20B04SIM7600M22"))

        assert device.get_version() == "LE20B04SIM7600M22"


class TestModes:
    def test_limit_to_lte_reboots(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CNMP=38"), at_response("AT+CFUN=1,1"))

        assert device.limit_to_lte() is True
        assert sent(port) == ["AT+CNMP=38", "AT+CFUN=1,1"]

    def test_limit_to_lte_failure(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CNMP=38", status="ERROR"))

        assert device.limit_to_lte() is False
        assert sent(port) == ["AT+CNMP=38"]

    @pytest.mark.parametrize(
        "method, pid",
        [("enable_rndis_mode", 9011), ("enable_qmi_mode", 9001), ("enable_ppp_mode", 9003)],
    )
    def test_usb_mode_switch(self, make_device, method, pid):
        command = f"AT+CUSBPIDSWITCH={pid},1,1"
        device, port = sim7600(make_device, at_response(command))

        assert getattr(device, method)() is True
        assert sent(port) == [command]

    def test_usb_mode_switch_failure(self, make_device):
        device, port = sim7600(make_device, at_response("AT+CUSBPIDSWITCH=9011,1,1", status="ERROR"))

        assert device.enable_rndis_mode() is False
