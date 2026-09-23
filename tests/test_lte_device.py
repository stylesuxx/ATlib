import pytest

from atlib.errors import ATCommandError
from atlib.LTE_Device import LTE_Device
from atlib.named_tuples import Address, Context, SignalQualityInfo
from atlib.Status import Status

from fake_serial import at_response


def lte(make_device, *responses):
    return make_device(LTE_Device, list(responses))


def sent(port) -> list[str]:
    return port.commands()[3:]


class TestSignalQuality:
    def test_rsrq_and_rsrp(self, make_device):
        device, port = lte(make_device, at_response("AT+CESQ", "+CESQ: 99,99,255,255,20,50"))

        assert device.get_signal_quality() == SignalQualityInfo(rsrp=50, rsrq=20)

    def test_error_answer(self, make_device):
        device, port = lte(make_device, at_response("AT+CESQ", status="ERROR"))

        with pytest.raises(ATCommandError):
            device.get_signal_quality()


class TestContexts:
    def test_two_contexts(self, make_device):
        device, port = lte(
            make_device,
            at_response(
                "AT+CGDCONT?",
                '+CGDCONT: 1,"IP","internet","0.0.0.0",0,0,0,0',
                '+CGDCONT: 2,"IPV4V6","","",0,0,0,0',
            ),
        )

        assert device.get_contexts() == [
            Context(1, "IP", "internet", "0.0.0.0"),
            Context(2, "IPV4V6", "", ""),
        ]

    def test_no_contexts(self, make_device):
        device, port = lte(make_device, at_response("AT+CGDCONT?"))

        assert device.get_contexts() == []

    def test_short_context_line_is_padded(self, make_device):
        device, port = lte(make_device, at_response("AT+CGDCONT?", '+CGDCONT: 1,"IP"'))

        assert device.get_contexts() == [Context(1, "IP", "", "")]

    def test_delete_context(self, make_device):
        device, port = lte(make_device, at_response("AT+CGDCONT=1"))

        assert device.delete_context(1) == Status.OK
        assert sent(port) == ["AT+CGDCONT=1"]

    def test_set_context_writes_arguments_verbatim(self, make_device):
        device, port = lte(make_device, at_response('AT+CGDCONT=1,"IP","internet"'))

        assert device.set_context(1, '"IP"', '"internet"') == Status.OK
        assert sent(port) == ['AT+CGDCONT=1,"IP","internet"']

    def test_activate_context(self, make_device):
        device, port = lte(make_device, at_response("AT+CGACT=1,1"))

        assert device.activate_context(1) == Status.OK
        assert sent(port) == ["AT+CGACT=1,1"]


class TestAddresses:
    def test_addresses_with_and_without_ip(self, make_device):
        device, port = lte(
            make_device,
            at_response("AT+CGPADDR", '+CGPADDR: 1,"10.64.12.3"', "+CGPADDR: 2"),
        )

        assert device.get_addresses() == [Address(1, "10.64.12.3"), Address(2, None)]
