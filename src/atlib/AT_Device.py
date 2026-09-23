import codecs
import time

from serial import Serial

from .Response import Response
from .setup_logger import logger
from .Status import Status


class AT_Device:
    """
    Base class for all device with AT commands.
    For higher level GSM features, use GSM_Device.
    """

    POLL_INTERVAL = 0.01
    # Unsolicited result codes kept for await_urc(); the oldest are dropped
    # beyond this many.
    UNSOLICITED_CAPACITY = 64

    def __init__(self, path: str, baudrate: int = 9600):
        """ Open AT device. Nothing else. """
        self.serial = None
        self._unsolicited: list[str] = []
        # A partial line the last read left behind, prepended to the next.
        self._carry = ""
        self.serial = Serial(path, timeout=0.5, baudrate=baudrate)
        if self.serial:
            logger.debug(f"AT serial device opened at {path}")

            # Enable command echo to be able to properly filter out URCs
            self._execute("ATE1")

            # Report numeric +CME ERROR codes (3GPP TS 27.007, AT+CMEE=1) so
            # CMEError.code is set regardless of the device's default mode.
            self._execute("AT+CMEE=1")

    def __del__(self):
        """ Close AT device. """
        if self.serial:
            self.serial.close()

    def write(self, cmd: str, endline: bool = True) -> str:
        """
        Write a single line to the serial port.

        Complete lines the device sent since the last read are kept for
        await_urc(); a partial line and undecodable bytes are dropped.
        """
        logger.debug(f"WRITE: {cmd}")
        if endline:
            cmd += "\r\n"

        encoded = cmd.encode()

        self._collect_pending_input()
        self.serial.write(encoded)

        return Status.OK

    def write_ctrlz(self) -> str:
        logger.debug("WRITE: Ctrl-Z")
        self.serial.write(bytes([26]))

        return Status.OK

    def command(self, cmd: str, timeout: float = 10, stopterm: str = "") -> Response:
        """
        Write a command and read its whole response.

        Nothing is raised here. Callers inspect the Response, or call its
        raise_for_status() when a failure should propagate. Unsolicited lines
        in the response are kept for await_urc().
        """
        self.write(cmd)
        text, outcome = self._receive(timeout, stopterm, command=cmd)
        tokens = self._lines(text)
        if outcome is not None:
            tokens.append(outcome)

        response = Response(tokens, cmd)
        self._file_unsolicited(response.unsolicited)

        return response

    def await_urc(self, marker: str, timeout: float = 10) -> str | None:
        """
        Wait for an unsolicited result code containing marker and return it.

        Lines the device sent earlier are checked first, then the port is read
        until a matching line arrives. Returns None when none arrives within
        timeout. The returned line is consumed; other lines stay for later calls.
        """
        deadline = time.monotonic() + timeout
        line = self._take_unsolicited(marker)
        while line is None and time.monotonic() < deadline:
            text, _ = self._receive(deadline - time.monotonic(), marker=marker)
            self._file_unsolicited(self._complete_lines(text))
            line = self._take_unsolicited(marker)

        return line

    def read(self, timeout: float = 10, stopterm: str = "") -> list[str]:
        """
        Read a single whole response from an AT command.
        Returns a list of tokens for parsing. When the response never
        completes, the list is the text so far followed by the status.
        """
        text, outcome = self._receive(timeout, stopterm)
        if outcome is None:
            return self.tokenize_response(text)

        if outcome == Response.UNDECODABLE:
            return [text, Status.ERROR]

        return [text, Status.TIMEOUT]

    def read_status(self, msg: str = "", timeout: float = 10) -> str:
        status = self.read(timeout)[-1]
        if status != Status.OK and status != Status.PROMPT:
            logger.debug(f"{status}: {msg}")

        return status

    @staticmethod
    def has_terminator(response: str, stopterm: str = "") -> bool:
        """ Return True if response is final. """
        return AT_Device._is_complete(response, stopterm)

    @staticmethod
    def tokenize_response(response: str) -> list[str]:
        """
        The non-empty lines of a response, with lines before the command echo
        dropped. The echo is taken to be the first line not starting with "+".
        """
        tokens = []
        found_echo = False
        for line in AT_Device._lines(response):
            if not found_echo and line.startswith("+"):
                continue

            found_echo = True
            tokens.append(line)

        return tokens

    def sync_baudrate(self, retry: bool = True) -> str:
        """
        Synchronize the device baudrate to the port.
        You should always call this first. Returns status.
        """
        logger.debug(f"Performing baudrate sync, retry={str(retry):s}")
        # Write AT and test whether received OK response.
        # A broken serial port will not reply.
        status = Status.TIMEOUT
        while status != Status.OK:
            status = self._execute("AT", timeout=5)
            if status == Status.OK:
                logger.debug("Succesful")
            elif not retry:
                logger.debug("Failure")
                break
            else:
                logger.debug("-> Retrying")

        return status

    def reset_state(self) -> str:
        """
        Ensures the state of the AT device is on par for a new environment.

        Some devices answer nothing at all until they have seen a bare AT, so
        the callers that talk to the SIM or the SMS store run this first.
        """
        # Read all remaining bytes.
        if self.serial.in_waiting > 0:
            self.serial.read(self.serial.in_waiting)

        # Write AT status message.
        for _ in range(0, 10):
            status = self._execute("AT")
            if status == Status.OK:
                break

    def _execute(self, cmd: str, description: str = "", timeout: float = 10) -> str:
        """
        Run a command whose answer is only its final result code and return
        that code, logging anything other than OK or the SMS prompt.
        """
        response = self.command(cmd, timeout)
        status = response.final
        if status == Response.UNDECODABLE:
            status = Status.ERROR

        if status != Status.OK and status != Status.PROMPT:
            logger.debug(f"{status}: {description}")

        return status

    def _receive(
        self, timeout: float, stopterm: str = "", command: str = "", marker: str = ""
    ) -> tuple[str, str | None]:
        """
        Read from the port until the text is complete, the deadline passes, or
        the bytes stop decoding. Returns the text and the outcome: None when
        complete, else Status.TIMEOUT or Response.UNDECODABLE.

        The text is complete when it holds a response to command (see
        _is_complete) or, with a marker, a complete line containing it. A
        partial trailing line is held back for the next read.
        """
        text = self._carry
        self._carry = ""
        deadline = time.monotonic() + timeout
        # A multibyte character may be split across two serial reads. The
        # incremental decoder holds the incomplete tail until the rest arrives.
        decoder = codecs.getincrementaldecoder("utf-8")()
        while time.monotonic() <= deadline:
            available = self.serial.in_waiting
            if available > 0:
                try:
                    text += decoder.decode(self.serial.read(available))
                except UnicodeDecodeError:
                    logger.debug(f"READ: {text}")
                    return (text, Response.UNDECODABLE)

                if marker != "":
                    complete = any(marker in line for line in self._complete_lines(text))
                else:
                    complete = self._is_complete(text, stopterm, command)

                if complete:
                    logger.debug(f"READ: {text}")
                    return (self._hold_back_partial_line(text, stopterm), None)

            time.sleep(self.POLL_INTERVAL)

        return (text, Status.TIMEOUT)

    def _hold_back_partial_line(self, text: str, stopterm: str) -> str:
        """
        Move a partial trailing line into the carry-over, unless it is the SMS
        prompt or holds the stopterm the caller waited for.
        """
        complete, tail = self._split_partial_line(text)
        if tail == "" or text.endswith(Status.PROMPT) or (stopterm != "" and stopterm in tail):
            return text

        self._carry = tail

        return complete

    def _collect_pending_input(self) -> None:
        """ Keep the complete lines the device sent since the last read. """
        self._carry = ""
        available = self.serial.in_waiting
        if available <= 0:
            return

        try:
            text = self.serial.read(available).decode("utf-8")
        except UnicodeDecodeError:
            return

        self._file_unsolicited(self._complete_lines(text))

    def _file_unsolicited(self, lines: list[str]) -> None:
        self._unsolicited.extend(lines)
        del self._unsolicited[:-self.UNSOLICITED_CAPACITY]

    def _take_unsolicited(self, marker: str) -> str | None:
        for index, line in enumerate(self._unsolicited):
            if marker in line:
                return self._unsolicited.pop(index)

        return None

    @staticmethod
    def _is_complete(text: str, stopterm: str = "", command: str = "") -> bool:
        """
        True once the text contains the stopterm, ends in the SMS prompt, or
        holds a final result code on a complete line after the echo of
        command. Lines after that code are unsolicited and never delay the
        response.
        """
        if stopterm != "" and stopterm in text:
            return True

        if text.endswith(Status.PROMPT):
            return True

        lines = AT_Device._complete_lines(text)
        if command != "" and command in lines:
            lines = lines[lines.index(command) + 1:]

        return any(Response.is_final_line(line) for line in lines)

    @staticmethod
    def _split_partial_line(text: str) -> tuple[str, str]:
        """ The text up to and including its last line break, and what follows. """
        end = text.rfind("\r\n")
        if end < 0:
            return ("", text)

        return (text[:end + 2], text[end + 2:])

    @staticmethod
    def _complete_lines(text: str) -> list[str]:
        """ The non-empty lines that end in a line break. """
        complete, _ = AT_Device._split_partial_line(text)

        return AT_Device._lines(complete)

    @staticmethod
    def _lines(text: str) -> list[str]:
        """ The non-empty lines of a response with carriage returns removed. """
        return [line for line in (raw.replace("\r", "") for raw in text.split("\r\n")) if line != ""]
