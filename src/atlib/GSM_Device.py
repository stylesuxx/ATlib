from time import sleep

from .SMS_Group import SMS_Group
from .Status import Status
from .AT_Device import AT_Device
from .setup_logger import logger


class GSM_Device(AT_Device):
    """ A class that provides higher level GSM features such
    as sending/receiving SMS and unlocking sim pin."""

    def __init__(self, path, baudrate=9600):
        """ Open GSM Device. Device sim still needs to be unlocked. """
        logger.debug("Opening GSM device")
        super().__init__(path, baudrate)
        while self.sync_baudrate() != Status.OK:
            sleep(1)

    def reboot(self):
        """ Reboot the GSM device. Returns status. """
        logger.debug("Rebooting GSM device")
        self.write("AT+CFUN=1,1")
        return self.read_status("Rebooting")

    def get_sim_status(self):
        """ Returns status of sim lock. True of locked. """
        self.reset_state()
        self.write("AT+CPIN?")
        resp = self.read()
        if "READY" in resp[1]:
            return Status.OK
        if "SIM PUK" in resp[1]:
            return Status.ERROR_SIM_PUK
        return Status.UNKNOWN

    def unlock_sim(self, pin):
        """ Unlocks the sim card using pin. Can block for a long time.
        Returns status."""
        self.reset_state()
        # Test whether sim is already unlocked.
        if self.get_sim_status() == Status.OK:
            return Status.OK

        # Unlock sim.
        logger.debug("Trying SIM pin={:s}".format(pin))
        self.write("AT+CPIN={:s}".format(pin))
        status = self.read_status("Setting pin")
        if status != Status.OK:
            return status

        # Wait until unlocked.
        logger.debug("Awaiting SMS ready status")
        self.read(stopterm="SMS Ready")
        logger.debug("Sim unlocked")
        return Status.OK

    def send_sms(self, nr, msg):
        """ Sends a text message to specified number.
        Returns status."""
        self.reset_state()
        # Set text mode.
        logger.debug("Sending \"{:s}\" to {:s}.".format(msg, nr))
        self.write("AT+CMGF=1")
        status = self.read_status("Text mode")
        if status != Status.OK:
            return status

        # Write message.
        self.write("AT+CMGS=\"{:s}\"".format(nr))
        status = self.read_status("Set number")
        if status != Status.PROMPT:
            return status

        self.write(msg)
        self.read()
        self.write_ctrlz()
        status = self.read_status("Sending message")

        logger.debug("Message sent.")
        return status

    def receive_sms(self, group=SMS_Group.UNREAD):
        """ Receive text messages. See types of message from SMS_Group class. """
        self.reset_state()
        # Read unread. After reading they will not show up here anymore!
        logger.debug("Scanning {:s} messages...".format(group))
        self.write("AT+CMGF=1")
        status = self.read_status("Text mode")
        if status != Status.OK:
            return status

        # Read the messages.
        self.write("AT+CMGL=\"{:s}\"".format(group))
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

    def delete_read_sms(self):
        """ Delete all messages except unread. Including drafts. """
        self.reset_state()
        self.write("AT+CMGD=1,3")
        return self.read_status("Deleting message")
