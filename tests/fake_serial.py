import typing

# One scripted response: a single burst, or several bursts delivered one per
# read cycle. A burst is what the modem sends in one go.
Response = typing.Union[str, typing.Sequence[str]]


class FakeSerial:
    """
    Stand-in for serial.Serial that plays scripted modem responses.

    Each write of a command line consumes the next scripted response and makes
    it readable. Responses are exact wire content, echo included, so tests see
    what the parser sees. A response given as a sequence of strings arrives as
    separate bursts: `in_waiting` only reports the current burst, so a reader
    that stops at a terminator leaves the following bursts for its next call.
    `chunk_size` limits how many bytes a single read returns, which exercises
    partial delivery in AT_Device.read().
    """

    def __init__(self, responses: typing.Iterable[Response] = (), chunk_size: int | None = None):
        self.responses: list[list[bytes]] = [self._bursts(response) for response in responses]
        self.chunk_size = chunk_size
        self.bursts: list[bytes] = []
        self.written: list[bytes] = []
        self.is_open = True

    @staticmethod
    def _bursts(response: Response) -> list[bytes]:
        if isinstance(response, str):
            return [response.encode()]

        return [burst.encode() for burst in response]

    @property
    def in_waiting(self) -> int:
        while self.bursts and not self.bursts[0]:
            self.bursts.pop(0)

        if not self.bursts:
            return 0

        if self.chunk_size is None:
            return len(self.bursts[0])

        return min(self.chunk_size, len(self.bursts[0]))

    def read(self, size: int = 1) -> bytes:
        if not self.bursts:
            return b""

        data, self.bursts[0] = self.bursts[0][:size], self.bursts[0][size:]
        return data

    def write(self, data: bytes) -> int:
        self.written.append(data)
        if self.responses:
            self.bursts.extend(self.responses.pop(0))

        return len(data)

    def reset_input_buffer(self) -> None:
        self.bursts = []

    def close(self) -> None:
        self.is_open = False

    def queue(self, data: str) -> None:
        """ Make data readable without a preceding write, like a URC. """
        self.bursts.append(data.encode())

    def commands(self) -> list[str]:
        """ Every written line, decoded and stripped of its line ending. """
        return [data.decode("utf-8", errors="replace").rstrip("\r\n") for data in self.written]


def at_response(command: str, *lines: str, status: str = "OK") -> str:
    """
    Build the wire content a modem sends for a command with echo enabled.

    The echo ends in a bare carriage return. Every information line and the
    final result code, verbose errors included, is wrapped in its own line
    breaks. A status of "> " builds the SMS prompt instead.
    """
    body = "".join(f"\r\n{line}\r\n" for line in lines)
    if status == "> ":
        return f"{command}\r{body}\r\n> "

    return f"{command}\r{body}\r\n{status}\r\n"
