#!/bin/python
# Console SMS sender using ATlib.
from atlib import GSM_Device


device = "/dev/serial0"
gsm = GSM_Device(device)

manufacturer = gsm.get_manufacturer()
model = gsm.get_model()
version = gsm.get_version()
imei = gsm.get_imei()
imsi = gsm.get_imsi()
serial = gsm.get_serial()
iccid = gsm.get_iccid()

print(f"Manufacturer: {manufacturer}")
print(f"Model: {model}")
print(f"Version: {version}")
print(f"IMEI: {imei}")
print(f"IMSI: {imsi}")
print(f"Serial: {serial}")
print(f"ICCID: {iccid}")
