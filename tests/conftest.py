import sys

import pytest

from atlib.GSM_Device import GSM_Device

from fake_serial import FakeSerial, at_response

OPEN_AT_DEVICE = [at_response("ATE1"), at_response("AT+CMEE=1")]
OPEN_GSM_DEVICE = OPEN_AT_DEVICE + [at_response("AT")]


@pytest.fixture
def make_device(monkeypatch):
    """
    Build a device over a FakeSerial.

    The responses needed by the constructor are prepended, so a test only
    scripts the responses for the commands it sends itself. Returns the
    device and the fake port.
    """
    def factory(device_class=GSM_Device, responses=(), chunk_size=None, **kwargs):
        if issubclass(device_class, GSM_Device):
            setup = OPEN_GSM_DEVICE
        else:
            setup = OPEN_AT_DEVICE

        port = FakeSerial(setup + list(responses), chunk_size=chunk_size)
        # The package re-exports the class under the module name, so the
        # module itself is only reachable through sys.modules.
        module = sys.modules["atlib.AT_Device"]
        monkeypatch.setattr(module, "Serial", lambda *args, **kwargs: port)
        device = device_class("/dev/fake", **kwargs)
        return device, port

    return factory
