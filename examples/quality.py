#!/bin/python
# Display signal quality information
from atlib import GSM_Device


device = "/dev/serial0"


def get_quality(rssi: int) -> float:
    """Maps RSSI to a percentage of quality."""
    if rssi == 99:
        return 0.0

    return (rssi / 31.0) * 100


gsm = GSM_Device(device)
rssi, ber = gsm.get_signal()
quality = get_quality(rssi)


print(f"RSSI: {rssi}")
print(f"BER: {ber}")
print(f"Quality: {quality:.0f}%")
