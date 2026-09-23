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

    def __init__(self, path: str, baudrate: int = 9600):
        """ Open AT device. Nothing else. """
        self.serial = None
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

        NOTE: Input buffer is cleared before writing in order to get rid of
              garbage and pending URCs.
        """
        logger.debug(f"WRITE: {cmd}")
        if endline:
            cmd += "\r\n"

        encoded = cmd.encode()

        self.serial.reset_input_buffer()
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
        raise_for_status() when a failure should propagate.
        """
        self.write(cmd)
        text, outcome = self._receive(timeout, stopterm)
        tokens = self._lines(text)
        if outcome is not None:
            tokens.append(outcome)

        return Response(tokens, cmd)

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

    def _receive(self, timeout: float, stopterm: str) -> tuple[str, str | None]:
        """
        Read from the port until the response is complete, the deadline
        passes, or the bytes stop decoding. Returns the text and the outcome:
        None when complete, else Status.TIMEOUT or Response.UNDECODABLE.
        """
        text = ""
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

                if self._is_complete(text, stopterm):
                    logger.debug(f"READ: {text}")
                    return (text, None)

            time.sleep(self.POLL_INTERVAL)

        return (text, Status.TIMEOUT)

    @staticmethod
    def _is_complete(text: str, stopterm: str = "") -> bool:
        if stopterm != "" and stopterm in text:
            return True

        if text.endswith(Status.PROMPT):
            return True

        if not text.endswith("\r\n"):
            return False

        lines = AT_Device._lines(text)

        return bool(lines) and Response.is_final_line(lines[-1])

    @staticmethod
    def _lines(text: str) -> list[str]:
        """ The non-empty lines of a response with carriage returns removed. """
        return [line for line in (raw.replace("\r", "") for raw in text.split("\r\n")) if line != ""]
