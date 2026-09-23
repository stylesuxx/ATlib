"""
Unsolicited result codes: captured by the device and consumed with await_urc.
"""
from atlib.AT_Device import AT_Device
from atlib.Status import Status

from fake_serial import at_response


class TestCapture:
    def test_urc_after_ok_in_the_same_burst_is_not_a_timeout(self, make_device):
        device, port = make_device(AT_Device, ["AT+CFUN=0\r\r\nOK\r\n\r\n+CGEV: ME DETACH\r\n"])

        response = device.command("AT+CFUN=0")

        assert response.status == Status.OK
        assert response.unsolicited == ["+CGEV: ME DETACH"]
        assert device.await_urc("DETACH", timeout=0) == "+CGEV: ME DETACH"

    def test_urc_before_the_echo_reaches_the_inbox(self, make_device):
        device, port = make_device(AT_Device, ["\r\nRING\r\n" + at_response("AT+CSQ", "+CSQ: 20,0")])

        device.command("AT+CSQ")

        assert device.await_urc("RING", timeout=0) == "RING"

    def test_pending_input_is_kept_by_the_next_write(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT")])
        port.queue("\r\n+CREG: 1\r\n")

        device.command("AT")

        assert device.await_urc("+CREG", timeout=0) == "+CREG: 1"

    def test_pending_garbage_is_discarded(self, make_device):
        device, port = make_device(AT_Device, [at_response("AT")])
        port.bursts.append(b"\xff\xfe\r\n")

        assert device.command("AT").is_ok
        assert device.await_urc("", timeout=0) is None


class TestAwaitUrc:
    def test_reads_the_port_until_the_marker_arrives(self, make_device):
        device, port = make_device(AT_Device)
        port.queue("\r\nRING\r\n")

        assert device.await_urc("RING", timeout=1) == "RING"

    def test_returns_none_on_timeout(self, make_device):
        device, port = make_device(AT_Device)

        assert device.await_urc("RING", timeout=0.05) is None

    def test_matched_line_is_consumed_and_others_stay(self, make_device):
        device, port = make_device(AT_Device)
        port.queue("\r\n+CREG: 1\r\n\r\nRING\r\n")

        assert device.await_urc("RING", timeout=1) == "RING"
        assert device.await_urc("RING", timeout=0) is None
        assert device.await_urc("+CREG", timeout=0) == "+CREG: 1"

    def test_partial_line_is_not_matched(self, make_device):
        device, port = make_device(AT_Device)
        port.queue("\r\nRIN")

        assert device.await_urc("RING", timeout=0.05) is None

    def test_inbox_is_bounded(self, make_device):
        device, port = make_device(AT_Device)
        port.queue("".join(f"\r\n+CREG: {number:02d}\r\n" for number in range(70)))

        device.await_urc("+CREG: 69", timeout=1)

        assert device.await_urc("+CREG: 05", timeout=0) is None
        assert device.await_urc("+CREG: 06", timeout=0) == "+CREG: 06"
