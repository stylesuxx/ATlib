import time
import typing
import re

from .SMS_Group import SMS_Group
from .Status import Status
from .AT_Device import AT_Device
from .Operator import Operator
from .setup_logger import logger
from .helpers import is_valid_operator, sanitize_operator


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
        self.write("AT+CFUN=1,1")

        return self.read_status("Rebooting")

    def off(self) -> str:
        self.write("AT+CFUN=0")
        resp = self.read(10, "DETACH")

        if resp[1] == "OK":
            return Status.OK

        return Status.ERROR

    def get_sim_status(self) -> str:
        """ Returns status of sim lock. """
        self.reset_state()
        self.write("AT+CPIN?")
        resp = self.read()

        if "READY" in resp[1]:
            return Status.OK

        if "SIM PUK" in resp[1]:
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
        self.write(f"AT+CPIN={pin}")
        status = self.read_status("Setting pin")
        if status != Status.OK:
            return status

        # Wait until unlocked.
        logger.debug("Awaiting SMS ready status")
        self.read(stopterm="SMS Ready")
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

        self.write("AT+CSCS=\"GSM\"")
        status = self.read_status("Character set GSM")
        if status != Status.OK:
            return status

        self.write("AT+CMGF=1")
        status = self.read_status("Text mode")
        if status != Status.OK:
            return status

        self.write(f"AT+CSMP=17,167,0,{dcs}")
        status = self.read_status("SMS mode")
        if status != Status.OK:
            return status

        self.write(f"AT+CMGS=\"{nr}\"")
        status = self.read_status("Set number")
        if status != Status.PROMPT:
            return status

        self.write(msg, endline=False)
        # self.read()
        self.write_ctrlz()
        status = self.read_status("Sending message")

        logger.debug("Message sent.")
        return status

    def receive_sms(self, group: str = SMS_Group.UNREAD) -> typing.List[str]:
        """
        Receive text messages.
        See types of message from SMS_Group class.
        """
        logger.debug(f"Scanning {group} messages...")

        self.reset_state()

        self.write("AT+CSCS=\"GSM\"")
        status = self.read_status("Character set GSM")
        if status != Status.OK:
            return status

        self.write("AT+CMGF=1")
        status = self.read_status("Text mode")
        if status != Status.OK:
            return status

        # Read the messages.
        self.write(f"AT+CMGL=\"{group}\"")
        resp = self.read()
        if resp[-1] != Status.OK:
            return resp[-1]

        # TotalElements = 2 + 2 * TotalMessages.
        # First and last elements are echo/result.
        table = []
        for i in range(1, len(resp) - 1, 2):
            header = resp[i].split(",")
            message = resp[i + 1]

            # Extract elements and strip garbage.
            sender = header[2].replace("\"", "")
            date = header[4].replace("\"", "")
            time = header[5].split("+")[0]
            el = [sender, date, time, message]
            table.append(el)
        return table

    def delete_read_sms(self) -> str:
        """ Delete all messages except unread. Including drafts. """
        self.reset_state()
        self.write("AT+CMGD=1,3")
        return self.read_status("Deleting message")

    def get_current_operator(self) -> str:
        """ Get current operator string. """
        self.write("AT+COPS?")
        resp = self.read()
        fields = resp[1].split(":")[1].strip()
        fields = fields.split(",")

        if len(fields) < 3:
            return None

        operator = fields[2].strip().strip('"')
        if operator == 0:
            return None

        return operator

    def get_available_operators(self) -> typing.List[Operator]:
        self.write("AT+COPS=?")
        resp = self.read(timeout=30)
        operators = resp[1].split(":")[1].strip()
        operators = operators.split("),")
        operators = list(map(lambda x: re.sub(r',?\(|\)', '', x), operators))
        operators = list(filter(is_valid_operator, operators))
        operators = list(map(lambda x: sanitize_operator(x), operators))

        return operators

    def set_operator(self, short: str) -> str:
        """ Set Operator by short name"""
        self.write(f"AT+COPS=1,1,\"{short}\"")
        return self.read_status()

    def set_operator_auto(self) -> str:
        """ Operator should be chosen automatically. """
        self.write("AT+COPS=0")
        return self.read_status()

    def call(self, nr: str, show_caller_id: bool = True) -> str:
        """
        Call a given number.
        By default caller ID is enabled.
        """
        caller_id = "i"
        if not show_caller_id:
            caller_id = "I"
        self.write(f"ATD{nr}{caller_id};")
        return self.read_status()

    def disconnect(self) -> str:
        """ Hang up. """
        self.write("AT+CHUP")
        return self.read_status()

    def accept_call(self):
        """ Accept call. """
        self.write("ATA")
        return self.read_status()

    def wait_for_call(self):
        """ Wait for a call, blocks until RING. """
        """
        AT+CLIP=1 should enable the caller identification, this does not work
        on SIM7070G though

        TODO: Test if it works on SIM800
        """
        while True:
            result = self.read()
            if "RING" in result[0]:
                return

    def get_signal(self) -> typing.Tuple[int, int]:
        """
        Get signal strength and Quality

        Higher RSSI is better (0-31), lower BER is better (0-7).

        if one or both of the values are 99, signal is not known
        """
        self.write("AT+CSQ")
        resp = self.read()
        rssi, ber = resp[1].split(":")[1].strip().split(",")

        return (int(rssi), int(ber))

    def get_manufacturer(self) -> str:
        """ Get manufacturer name."""
        self.write("AT+CGMI")
        resp = self.read()
        value = resp[1].split(":")[1].strip().replace("\"", "")
        return value

    def get_model(self) -> str:
        """ Get model name."""
        self.write("AT+CGMM")
        resp = self.read()
        value = resp[1].split(":")[1].strip().replace("\"", "")
        return value

    def get_serial(self) -> str:
        """ Get serial number."""
        self.write("AT+CGSN")
        resp = self.read()
        value = resp[1].strip()
        return value

    def get_iccid(self) -> str:
        """ Get ICCID."""
        self.write("AT+ICCID")
        resp = self.read()
        value = resp[1].split(":")[1].strip().replace("\"", "")
        return value

    def get_version(self) -> str:
        """ Get version."""
        self.write("AT+VER")
        resp = self.read()
        value = resp[1].strip().replace("\"", "")
        return value

    def get_imei(self) -> str:
        """ Get IMEI."""
        self.write("AT+CGSN")
        resp = self.read()
        value = resp[1].strip().replace("\"", "")
        return value

    def get_imsi(self) -> str:
        """ Get IMSI."""
        self.write("AT+CIMI")
        resp = self.read()
        value = resp[1].strip().replace("\"", "")
        return value

    def get_gprs_status(self) -> str:
        self.write("AT+CGATT?")
        resp = self.read()
        value = resp[1].split(":")[1].strip().replace("\"", "")
        return value

    def get_network_registration(self) -> typing.Tuple[int, int]:
        self.write("AT+CREG?")
        resp = self.read()
        value = resp[1].split(":")[1].strip().replace("\"", "")
        n, stat = value.split(",")

        return (int(n), int(stat))
