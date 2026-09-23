import typing


class FakeSerial:
    """
    Stand-in for serial.Serial that plays scripted modem responses.

    Each write of a command line consumes the next scripted response and makes
    it readable. Responses are exact wire content, echo included, so tests see
    what the parser sees. `chunk_size` limits how many bytes a single read
    returns, which exercises partial delivery in AT_Device.read().
    """

    def __init__(self, responses: typing.Iterable[str] = (), chunk_size: int | None = None):
        self.responses: list[bytes] = [response.encode() for response in responses]
        self.chunk_size = chunk_size
        self.pending = b""
        self.written: list[bytes] = []
        self.is_open = True

    @property
    def in_waiting(self) -> int:
        if self.chunk_size is None:
            return len(self.pending)

        return min(self.chunk_size, len(self.pending))

    def read(self, size: int = 1) -> bytes:
        data, self.pending = self.pending[:size], self.pending[size:]
        return data

    def write(self, data: bytes) -> int:
        self.written.append(data)
        if self.responses:
            self.pending += self.responses.pop(0)

        return len(data)

    def reset_input_buffer(self) -> None:
        self.pending = b""

    def close(self) -> None:
        self.is_open = False

    def queue(self, data: str) -> None:
        """ Make data readable without a preceding write, like a URC. """
        self.pending += data.encode()

    def commands(self) -> list[str]:
        """ Every written line, decoded and stripped of its line ending. """
        return [data.decode().rstrip("\r\n") for data in self.written]


def at_response(command: str, *lines: str, status: str = "OK") -> str:
    """
    Build the wire content a modem sends for a command with echo enabled.

    Information lines come between echo and status. A status of "> " builds
    the SMS prompt. A status starting with "+" builds a verbose error, which
    has no blank line before it.
    """
    body = "".join(f"\r\n{line}\r\n" for line in lines)
    if status == "> ":
        return f"{command}\r\r\n> "

    if status.startswith("+"):
        return f"{command}\r{body}\r\n{status}\r\n"

    return f"{command}\r{body}\r\n{status}\r\n"
