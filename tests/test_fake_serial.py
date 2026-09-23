"""
Smoke tests proving the fake port drives the real AT_Device.read() loop.
"""
import pytest

from atlib.AT_Device import AT_Device
from atlib.GSM_Device import GSM_Device
from atlib.Status import Status

from fake_serial import at_response


def test_at_device_constructor_enables_echo(make_device):
    device, port = make_device(AT_Device)

    assert port.commands() == ["ATE1"]


def test_gsm_device_constructor_syncs_baudrate(make_device):
    device, port = make_device(GSM_Device)

    assert port.commands() == ["ATE1", "AT"]


def test_read_returns_tokens_with_status_last(make_device):
    device, port = make_device(AT_Device, [at_response("AT+CSQ", "+CSQ: 20,0")])

    device.write("AT+CSQ")
    assert device.read() == ["AT+CSQ", "+CSQ: 20,0", "OK"]


def test_read_assembles_chunked_delivery(make_device):
    device, port = make_device(AT_Device, [at_response("AT+CSQ", "+CSQ: 20,0")], chunk_size=3)

    device.write("AT+CSQ")
    assert device.read() == ["AT+CSQ", "+CSQ: 20,0", "OK"]


def test_read_times_out_without_response(make_device):
    device, port = make_device(AT_Device, [""])

    device.write("AT+CSQ")
    assert device.read(timeout=0.05) == ["", Status.TIMEOUT]


def test_write_discards_pending_input(make_device):
    device, port = make_device(AT_Device, [at_response("AT")])
    port.queue("+CREG: 1\r\n")

    device.write("AT")
    assert device.read() == ["AT", "OK"]
