#!/bin/python
# Console SMS sender using ATlib.

from atlib import GSM_Device, Status

import logging
logging.basicConfig(level=logging.DEBUG)

gsm = GSM_Device("/dev/serial0")
if gsm.get_sim_status() == Status.ERROR:
    pin = input("SIM Pin: ")
    gsm.unlock_sim(pin)
else:
    print("SIM already unlocked.")

while True:
    print("")
    nr = input("Phone number: ")
    msg = input("Message: ")

    if gsm.send_sms(nr, msg) != Status.OK:
        print("Error sending message.")
