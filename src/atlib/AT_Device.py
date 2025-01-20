from serial import Serial
import time
import typing

from .Status import Status
from .setup_logger import logger


class AT_Device:
    """
    Base class for all device with AT commands.
    For higher level GSM features, use GSM_Device.
    """

    def __init__(self, path: str, baudrate: int = 9600):
        """ Open AT device. Nothing else. """
        self.serial = Serial(path, timeout=0.5, baudrate=baudrate)
        logger.debug(f"AT serial device opened at {path}")

    def __del__(self):
        """ Close AT device. """
        self.serial.close()

    def write(self, cmd: str, endline: bool = True) -> str:
        """ Write a single line to the serial port. """
        logger.debug(f"WRITE: {cmd}")
        if endline:
            cmd += "\r\n"
        encoded = cmd.encode()
        self.serial.write(encoded)
        return Status.OK

    def write_ctrlz(self) -> str:
        """ Write the terminating CTRL-Z to end a prompt. """
        logger.debug("WRITE: Ctrl-Z")
        self.serial.write(bytes([26]))
        return Status.OK

    def has_terminator(response, stopterm: str = "") -> bool:
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
        return can_terminate

    def tokenize_response(response: str) -> typing.List[str]:
        """ Chop a response in pieces for parsing. """
        # First split by newline.
        table = response.split("\r\n")
        final_table = []

        for i in range(len(table)):
            # Remove trailing "\r".
            el = table[i].replace("\r", "")
            # Take only nonempty entries".
            if el != "":
                final_table.append(el)
        return final_table

    def read(self, timeout: int = 10, stopterm: str = "") -> typing.List[str]:
        """
        Read a single whole response from an AT command.
        Returns a list of tokens for parsing.
        """
        resp = ""
        start_time = time.time()
        delay = 0.01
        while True:
            avail = self.serial.in_waiting
            if avail > 0:
                # Read bytes and check if terminator is contained.
                # If it is not a utf-8 string, return error.
                try:
                    resp += self.serial.read(avail).decode("utf-8")
                except:
                    logger.debug(f"READ: {resp}")
                    return [resp, Status.ERROR]
                if AT_Device.has_terminator(resp, stopterm):
                    logger.debug(f"READ: {resp}")
                    table = AT_Device.tokenize_response(resp)
                    return table

            if time.time() - start_time > timeout:
                return [resp, Status.TIMEOUT]

            time.sleep(delay)

    def read_status(self, msg: str = "") -> str:
        """ Returns status of latest response. """
        status = self.read()[-1]
        if status != Status.OK and status != Status.PROMPT:
            logger.debug(f"{status}: {msg}")
        return status

    def sync_baudrate(self, retry: bool = True) -> str:
        """
        Synchronize the device baudrate to the port.
        You should always call this first. Returns status.
        """
        logger.debug("Performing baudrate sync, retry={:s}".format(str(retry)))
        # Write AT and test whether received OK response.
        # A broken serial port will not reply.
        while True:
            self.write("AT")
            status = self.read(timeout=5)[-1]
            if status == Status.OK:
                logger.debug("Succesful")
                return status
            elif retry:
                logger.debug("-> Retrying")
            else:
                logger.debug("Failure")

    def reset_state(self) -> str:
        """ Ensures the state of the AT device is on par for a new environment. """
        # Read all remaining bytes.
        if self.serial.in_waiting > 0:
            self.serial.read(self.serial.in_waiting)
        # Write AT status message.
        for i in range(0, 10):
            self.write("AT")
            status = self.read_status()
            if status == Status.OK:
                break
