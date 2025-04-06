#!/bin/python
# Console SMS sender using ATlib.
from atlib import AIR780EU


device = "/dev/serial0"
gsm = AIR780EU(device)


def rsrp_to_dbm(value: int) -> int:
    if value == 255:
        return -140  # Unknown
    return value - 140


def rsrq_to_dbm(value: int) -> float:
    if value == 255:
        return -20.0  # Unknown
    return (value * 0.5) - 19.5


def get_bars(rsrp_dbm: int) -> int:
    """Returns the number of bars based on the RSRP value."""
    if rsrp_dbm >= -80:
        return 5
    elif rsrp_dbm >= -90:
        return 4
    elif rsrp_dbm >= -100:
        return 3
    elif rsrp_dbm >= -110:
        return 2
    else:
        return 1


def classify_rsrq(rsrq_dbm: float) -> str:
    """Classify RSRQ (in dB) into quality tiers."""
    if rsrq_dbm >= -10:
        return "Excellent"
    elif rsrq_dbm >= -15:
        return "Good"
    elif rsrq_dbm >= -20:
        return "Fair"
    else:
        return "Poor"


manufacturer = gsm.get_manufacturer()
model = gsm.get_model()
version = gsm.get_version()
cell = gsm.get_cell_info()

signal_quality = gsm.get_signal_quality()
rsrq_dbm = rsrq_to_dbm(signal_quality.rsrq)
rsrp_dbm = rsrp_to_dbm(signal_quality.rsrp)


print(f"Manufacturer: {manufacturer}")
print(f"Model: {model}")
print(f"Version: {version}")
print(f"Cell: {cell}")
print(f"RSRP: {rsrp_dbm} dBm, RSRQ: {rsrq_dbm}dBm")
print(f"Quality: {get_bars(rsrp_dbm)}/5 ({classify_rsrq(rsrq_dbm)})")
