import re
import time

from .AT_Device import AT_Device
from .errors import CMEError
from .helpers import is_valid_operator, sanitize_operator
from .Operator import Operator
from .Response import Response
from .setup_logger import logger
from .SMS_Group import SMS_Group
from .Status import Status


class GSM_Device(AT_Device):
    """
    A class that provides higher level GSM features such as sending/receiving
    SMS and unlocking sim pin.

    This is a rather generic implementation and should be the base class for
    more specific implementations. It is to be assumed that all AT modems will
    understand the functionality within this file.
    """

    def __init__(self, path: str, baudrate: int = 9600):
        """ Open GSM Device. Device sim still needs to be unlocked. """
        logger.debug("Opening GSM device")
        super().__init__(path, baudrate)
        while self.sync_baudrate() != Status.OK:
            time.sleep(1)

    def reboot(self) -> str:
        """ Reboot the GSM device. Returns status. """
        logger.debug("Rebooting GSM device")
        return self._execute("AT+CFUN=1,1", "Rebooting")

    def off(self) -> str:
        # The detach URC that follows lands in the inbox for await_urc("DETACH").
        response = self.command("AT+CFUN=0")

        if response.is_ok:
            return Status.OK

        return Status.ERROR

    def get_sim_status(self) -> str:
        """ Returns status of sim lock. """
        self.reset_state()
        response = self.command("AT+CPIN?")

        # 3GPP TS 27.007: CME ERROR 10 is "SIM not inserted"
        if isinstance(response.error, CMEError) and response.error.code == 10:
            return Status.ERROR_SIM_NOT_INSERTED

        if not response.is_ok:
            return Status.UNKNOWN

        state = response.value("+CPIN")
        if "READY" in state:
            return Status.OK

        if "SIM PUK" in state:
            return Status.ERROR_SIM_PUK

        return Status.UNKNOWN

    def unlock_sim(self, pin: str) -> str:
        """
        Unlocks the sim card using pin. Can block for a long time.
        Returns status.
        """
        self.reset_state()
        # Test whether sim is already unlocked.
        if self.get_sim_status() == Status.OK:
            return Status.OK

        # Unlock sim.
        logger.debug(f"Trying SIM pin={pin}")
        status = self._execute(f"AT+CPIN={pin}", "Setting pin")
        if status != Status.OK:
            return status

        # Wait until unlocked.
        # SIM800 announces the SMS store with this line. Chips that never send
        # it run out the wait.
        logger.debug("Awaiting SMS ready status")
        self.await_urc("SMS Ready")
        logger.debug("Sim unlocked")
        return Status.OK

    def send_sms(self, nr: str, msg: str, dcs: int = 0) -> str:
        """
        Sends a text message to specified number.
        Returns status.

        dcs:
          - 0: Standard SMS
          -16: Flash
        """
        logger.debug(f"Sending \"{msg}\" to {nr}.")

        self.reset_state()

        status = self._execute("AT+CSCS=\"GSM\"", "Character set GSM")
        if status != Status.OK:
            return status

        status = self._execute("AT+CMGF=1", "Text mode")
        if status != Status.OK:
            return status

        status = self._execute(f"AT+CSMP=17,167,0,{dcs}", "SMS mode")
        if status != Status.OK:
            return status

        status = self._execute(f"AT+CMGS=\"{nr}\"", "Set number")
        if status != Status.PROMPT:
            return status

        self.write(msg, endline=False)
        self.write_ctrlz()
        # Delivery to the network can take a long time, SIMCom documents up to 60 s.
        status = self.read_status("Sending message", timeout=60)

        logger.debug("Message sent.")
        return status

    def receive_sms(self, group: str = SMS_Group.UNREAD) -> list[str]:
        """
        Receive text messages.
        See types of message from SMS_Group class.
        """
        logger.debug(f"Scanning {group} messages...")

        self.reset_state()

        status = self._execute("AT+CSCS=\"GSM\"", "Character set GSM")
        if status != Status.OK:
            return status

        status = self._execute("AT+CMGF=1", "Text mode")
        if status != Status.OK:
            return status

        # Read the messages.
        response = self.command(f"AT+CMGL=\"{group}\"")
        if not response.is_ok:
            return response.final

        # Each message is a +CMGL header followed by its body lines.
        table = []
        for line in response.lines:
            if line.startswith("+CMGL:"):
                fields = Response.split_fields(line.split(":", 1)[1])
                sender = fields[2]
                date, time_with_zone = fields[4].split(",")
                # The time carries a timezone offset in quarter hours, "10:15:32+08".
                time = time_with_zone[:8]
                table.append([sender, date, time, ""])
            elif table:
                message = table[-1]
                message[3] = line if message[3] == "" else f"{message[3]}\n{line}"
        return table

    def delete_read_sms(self) -> str:
        """ Delete all messages except unread. Including drafts. """
        self.reset_state()
        return self._execute("AT+CMGD=1,3", "Deleting message")

    def get_current_operator(self) -> str:
        """ Get current operator string. """
        fields = self.command("AT+COPS?").raise_for_status().fields("+COPS")

        if len(fields) < 3:
            return None

        return fields[2]

    def get_available_operators(self) -> list[Operator]:
        listing = self.command("AT+COPS=?", timeout=30).raise_for_status().value("+COPS")
        # Every parenthesised group is an operator, except the trailing lists
        # of supported modes and formats, which is_valid_operator drops.
        groups = re.findall(r"\(([^)]*)\)", listing)

        return [sanitize_operator(group) for group in groups if is_valid_operator(group)]

    def set_operator(self, short: str) -> str:
        """ Set Operator by short name"""
        # Network selection can take a long time, SIMCom documents up to 60 s.
        return self._execute(f"AT+COPS=1,1,\"{short}\"", timeout=60)

    def set_operator_auto(self) -> str:
        """ Operator should be chosen automatically. """
        return self._execute("AT+COPS=0")

    def call(self, nr: str, show_caller_id: bool = True) -> str:
        """
        Call a given number.
        By default caller ID is enabled.
        """
        caller_id = "i"
        if not show_caller_id:
            caller_id = "I"
        return self._execute(f"ATD{nr}{caller_id};")

    def disconnect(self) -> str:
        """ Hang up. """
        return self._execute("AT+CHUP")

    def accept_call(self):
        """ Accept call. """
        return self._execute("ATA")

    def wait_for_call(self):
        """ Wait for a call, blocks until RING. """
        """
        AT+CLIP=1 should enable the caller identification, this does not work
        on SIM7070G though

        TODO: Test if it works on SIM800
        """
        while self.await_urc("RING") is None:
            pass

    def get_signal(self) -> tuple[int, int]:
        """
        Get signal strength and Quality

        Higher RSSI is better (0-31), lower BER is better (0-7).

        if one or both of the values are 99, signal is not known
        """
        rssi, ber = self.command("AT+CSQ").raise_for_status().fields("+CSQ")

        return (int(rssi), int(ber))

    def get_manufacturer(self) -> str:
        """ Get manufacturer name."""
        return self.command("AT+CGMI").raise_for_status().value("+CGMI")

    def get_model(self) -> str:
        """ Get model name."""
        return self.command("AT+CGMM").raise_for_status().value("+CGMM")

    def get_serial(self) -> str:
        """ Get serial number, which is the IMEI on a GSM device. """
        return self.get_imei()

    def get_iccid(self) -> str:
        """ Get ICCID."""
        return self.command("AT+ICCID").raise_for_status().value("+ICCID")

    def get_imei(self) -> str:
        """ Get IMEI."""
        return self.command("AT+CGSN").raise_for_status().value("+CGSN")

    def get_imsi(self) -> str:
        """ Get IMSI."""
        return self.command("AT+CIMI").raise_for_status().value("+CIMI")

    def get_gprs_status(self) -> str:
        return self.command("AT+CGATT?").raise_for_status().value("+CGATT")

    def enable_location_reporting(self) -> str:
        """
        AT+CREG? requests will contain location information (Cell ID)

        NOTE: This will also enable +CREG URCs
        """
        if self.command("AT+CREG=2").is_ok:
            return Status.OK

        return Status.ERROR

    def get_registration_fields(self) -> list[str]:
        """
        The fields of the AT+CREG? answer: mode, registration state and, with
        location reporting enabled, location area code and cell id in hex.
        """
        return self.command("AT+CREG?").raise_for_status().fields("+CREG")

    def get_network_registration(self) -> tuple[int, int]:
        n, stat = self.get_registration_fields()[:2]

        return (int(n), int(stat))

    def get_cell_location(self) -> tuple[int, int, int, int]:
        n, stat, lac, cell_id = self.get_registration_fields()[:4]

        return (int(n), int(stat), int(lac, 16), int(cell_id, 16))
