import pytest

from atlib.AIR780EU import AIR780EU
from atlib.errors import ATCommandError
from atlib.named_tuples import CellInfo

from fake_serial import at_response

CCED = "+CCED:LTE current cell info:232,1,123456789,0,3,3,1300,12345678,-90,-10,1234,4,100"


def air(make_device, *responses):
    return make_device(AIR780EU, list(responses))


def sent(port) -> list[str]:
    return port.commands()[2:]


class TestCellInfo:
    def test_fields_map_onto_cell_info(self, make_device):
        device, port = air(make_device, at_response("AT+CCED=0,1", CCED))

        assert device.get_cell_info() == CellInfo(
            mcc=232, mnc=1, imsi=123456789, roaming_status=0, band=3, bandwidth_index=3,
            earfcn=1300, cell_id=12345678, rsrp=-90, rsrq=-10, tac=1234, signal_level=4, pcid=100,
        )

    def test_error_answer(self, make_device):
        device, port = air(make_device, at_response("AT+CCED=0,1", status="ERROR"))

        with pytest.raises(ATCommandError):
            device.get_cell_info()


class TestBands:
    def test_set_allowed_bands_builds_fdd_mask(self, make_device):
        device, port = air(make_device, at_response("AT*BAND=5,0,0,0,134742085,1,1,0"))

        device.set_allowed_bands([1, 3, 7, 20, 28])
        assert sent(port) == ["AT*BAND=5,0,0,0,134742085,1,1,0"]

    def test_set_allowed_bands_builds_tdd_mask(self, make_device):
        device, port = air(make_device, at_response("AT*BAND=5,0,0,160,0,1,1,0"))

        device.set_allowed_bands([38, 40])
        assert sent(port) == ["AT*BAND=5,0,0,160,0,1,1,0"]

    def test_allowed_bands_from_masks(self, make_device):
        device, port = air(make_device, at_response("AT*BAND?", "*BAND:5,0,0,0,134742213"))

        assert device.get_allowed_bands() == [1, 3, 7, 8, 20, 28]

    def test_allowed_bands_mixes_tdd_and_fdd(self, make_device):
        device, port = air(make_device, at_response("AT*BAND?", "*BAND:5,0,0,2,1"))

        assert device.get_allowed_bands() == [1, 34]

    def test_active_band(self, make_device):
        device, port = air(make_device, at_response("AT*BANDIND?", "*BANDIND: 0, 3, 7"))

        assert device.get_active_band() == 3


class TestVersion:
    def test_bare_version_string(self, make_device):
        device, port = air(make_device, at_response("AT+VER", "AirM2M_780EU_V1234"))

        assert device.get_version() == "AirM2M_780EU_V1234"
