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

    # Result codes that end a response like ERROR does, but carry a reason.
    VERBOSE_ERROR_PREFIXES = ("+CME ERROR", "+CMS ERROR")

    def __init__(self, path: str, baudrate: int = 9600):
        """ Open AT device. Nothing else. """
        self.serial = None
        self.serial = Serial(path, timeout=0.5, baudrate=baudrate)
        if self.serial:
            logger.debug(f"AT serial device opened at {path}")

            # Enable command echo to be able to properly filter out URCs
            self.write("ATE1")
            self.read_status()

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

    @staticmethod
    def has_terminator(response: str, stopterm: str = "") -> bool:
        """ Return True if response is final. """
        # If the string ends with one of these terms, then we stop reading.
        endterms = [
            "\r\nOK\r\n",
            "\r\nERROR\r\n",
            "> "
        ]

        # We can stop reading if either an endterm is detected or
        # the stopterm is inside the string which causes immediate halt.
        can_terminate = stopterm != "" and stopterm in response
        for s in endterms:
            if response.endswith(s):
                can_terminate = True
                break

        # A verbose error (+CME ERROR / +CMS ERROR) is a final response as well,
        # the device sends nothing after it. Detecting it here keeps a failing
        # command from waiting out the read timeout.
        if not can_terminate and response.endswith("\r\n"):
            last_line = response.rstrip("\r\n").split("\r\n")[-1]
            can_terminate = last_line.startswith(AT_Device.VERBOSE_ERROR_PREFIXES)

        return can_terminate

    @staticmethod
    def tokenize_response(response: str) -> list[str]:
        # First split by newline.
        table = response.split("\r\n")
        final_table = []

        found_echo = False
        for i in range(len(table)):
            # Remove trailing "\r".
            el = table[i].replace("\r", "")

            # Take only nonempty entries
            if el != "":
                # Drop + lines until we see the command echo
                if not found_echo:
                    if not el.startswith("+"):
                        found_echo = True
                        final_table.append(el)
                    # else: URC before command echo, drop it
                else:
                    # After command echo, keep everything
                    final_table.append(el)

        return final_table

    def read(self, timeout: int = 10, stopterm: str = "") -> list[str]:
        """
        Read a single whole response from an AT command.
        Returns a list of tokens for parsing.
        """
        resp = ""
        deadline = time.monotonic() + timeout
        delay = 0.01
        # A multibyte character may be split across two serial reads. The
        # incremental decoder holds the incomplete tail until the rest arrives.
        decoder = codecs.getincrementaldecoder("utf-8")()
        while time.monotonic() <= deadline:
            avail = self.serial.in_waiting
            if avail > 0:
                # Read bytes and check if terminator is contained.
                # If it is not a utf-8 string, return error.
                try:
                    resp += decoder.decode(self.serial.read(avail))
                except UnicodeDecodeError:
                    logger.debug(f"READ: {resp}")
                    return [resp, Status.ERROR]

                if AT_Device.has_terminator(resp, stopterm):
                    logger.debug(f"READ: {resp}")
                    table = AT_Device.tokenize_response(resp)
                    return table

            time.sleep(delay)

        return [resp, Status.TIMEOUT]

    def command(self, cmd: str, timeout: float = 10, stopterm: str = "") -> Response:
        """
        Write a command and read its whole response.

        Nothing is raised here. Callers inspect the Response, or call its
        raise_for_status() when a failure should propagate.
        """
        self.write(cmd)
        return Response(self.read(timeout, stopterm), cmd)

    def read_status(self, msg: str = "") -> str:
        status = self.read()[-1]
        if status != Status.OK and status != Status.PROMPT:
            logger.debug(f"{status}: {msg}")

        return status

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
            self.write("AT")
            status = self.read(timeout=5)[-1]
            if status == Status.OK:
                logger.debug("Succesful")
            elif not retry:
                logger.debug("Failure")
                break
            else:
                logger.debug("-> Retrying")

        return status

    def reset_state(self) -> str:
        """ Ensures the state of the AT device is on par for a new environment. """
        # Read all remaining bytes.
        if self.serial.in_waiting > 0:
            self.serial.read(self.serial.in_waiting)

        # Write AT status message.
        for _ in range(0, 10):
            self.write("AT")
            status = self.read_status()
            if status == Status.OK:
                break
