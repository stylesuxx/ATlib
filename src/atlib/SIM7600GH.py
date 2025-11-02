from typing import List
import re

from atlib import LTE_Device


class SIM7600GH(LTE_Device):
    def __init__(self, path: str, baudrate: int = 115200):
        super().__init__(path, baudrate)

    def get_allowed_bands(self) -> List[int]:
        """Get allowed LTE bands from CNBP configuration.

        Returns list of enabled LTE band numbers.
        """
        self.write("AT+CNBP?")
        response = self.read()
        # +CNBP: 0x100200000EE80380,0x480000000000000000000000000000000000000000000042000007FFFFDF3FFF,0x000000000000003F
        value = response[1].split(":")[1].strip()
        fields = value.split(",")

        # Second field is LTE bands
        lte_hex = fields[1].strip()

        # Convert hex to int (handle very large numbers)
        if lte_hex.startswith("0x"):
            lte_bitmask = int(lte_hex, 16)
        else:
            lte_bitmask = int(lte_hex, 16)

        bands = []
        for shift in range(72):
            if (lte_bitmask >> shift) & 1:
                bands.append(shift + 1)

        return bands

    def get_active_band(self) -> int:
        """Get currently active LTE band.

        Returns the active band number.
        """
        self.write("AT+CPSI?")
        response = self.read()
        # +CPSI: LTE,Online,310-410,0x7C11,12345678,456,EUTRAN-BAND3,1850,5,5,-98,-10,-65,15
        value = response[1].split(":")[1].strip()

        # Find the EUTRAN-BANDXX field
        match = re.search(r'EUTRAN-BAND(\d+)', value)
        if match:
            return int(match.group(1))

        # Fallback: try to find band in comma-separated fields
        fields = value.split(",")
        for field in fields:
            if "BAND" in field.upper():
                # Extract number from field like "EUTRAN-BAND3"
                band_match = re.search(r'(\d+)', field)
                if band_match:
                    return int(band_match.group(1))

        return 0  # Unknown/not connected

    def get_version(self) -> str:
        """Get firmware version."""
        self.write("AT+CGMR")
        response = self.read()

        return response[1].split(":")[1].strip()

    def limit_to_lte(self) -> bool:
        """Limit to LTE bands only and reset modem.

        Returns True if successful.
        """
        try:
            # Set to LTE only mode
            self.write("AT+CNMP=38")
            response = self.read()

            if "OK" in "".join(response):
                # Reset modem to apply settings
                self.write("AT+CFUN=1,1")
                self.read(timeout=10)  # Wait for reboot
                return True
            return False
        except Exception:
            return False

    def enable_rndis_mode(self) -> bool:
        """Enable RNDIS mode and reset modem.

        RNDIS creates usb0 interface - easiest plug-and-play mode.
        Returns True if successful.
        """
        try:
            self.write("AT+CUSBPIDSWITCH=9011,1,1")
            response = self.read()

            if "OK" in "".join(response):
                # Modem will automatically reset
                return True
            return False
        except Exception:
            return False

    def enable_qmi_mode(self) -> bool:
        """Enable QMI mode and reset modem.

        QMI creates wwan0 interface - modern protocol, best for ModemManager.
        Returns True if successful.
        """
        try:
            self.write("AT+CUSBPIDSWITCH=9001,1,1")
            response = self.read()

            if "OK" in "".join(response):
                # Modem will automatically reset
                return True
            return False
        except Exception:
            return False

    def enable_ppp_mode(self) -> bool:
        """Enable PPP mode and reset modem.

        PPP creates ppp0 interface - traditional dial-up style.
        Returns True if successful.
        """
        try:
            self.write("AT+CUSBPIDSWITCH=9003,1,1")
            response = self.read()

            if "OK" in "".join(response):
                # Modem will automatically reset
                return True

            return False

        except Exception:
            return False
