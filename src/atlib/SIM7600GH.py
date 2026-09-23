import re

from atlib.LTE_Device import LTE_Device


class SIM7600GH(LTE_Device):
    def __init__(self, path: str, baudrate: int = 115200):
        super().__init__(path, baudrate)

    def get_allowed_bands(self) -> list[int]:
        """Get allowed LTE bands from CNBP configuration.

        Returns list of enabled LTE band numbers.
        """
        # +CNBP: <GSM/WCDMA mask>,<LTE mask>,<TDS mask>, for example
        # 0x100200000EE80380,0x4800...07FFFFDF3FFF,0x000000000000003F
        fields = self.command("AT+CNBP?").raise_for_status().fields("+CNBP")

        # Second field is LTE bands
        lte_bitmask = int(fields[1], 16)

        bands = []
        for shift in range(72):
            if (lte_bitmask >> shift) & 1:
                bands.append(shift + 1)

        return bands

    def get_active_band(self) -> int:
        """Get currently active LTE band.

        Returns the active band number.
        """
        # +CPSI: LTE,Online,310-410,0x7C11,12345678,456,EUTRAN-BAND3,1850,5,5,-98,-10,-65,15
        value = self.command("AT+CPSI?").raise_for_status().value("+CPSI")

        match = re.search(r"BAND(\d+)", value, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return 0  # Unknown/not connected

    def get_version(self) -> str:
        """Get firmware version."""
        return self.command("AT+CGMR").raise_for_status().value("+CGMR")

    def limit_to_lte(self) -> bool:
        """Limit to LTE bands only and reset modem.

        Returns True if successful.
        """
        if not self.command("AT+CNMP=38").is_ok:
            return False

        self.reboot()
        return True

    def set_usb_mode(self, product_id: int) -> bool:
        """Switch the USB product id, which selects the network interface mode.

        The modem resets itself to apply the change. Returns True if accepted.
        """
        return self.command(f"AT+CUSBPIDSWITCH={product_id},1,1").is_ok

    def enable_rndis_mode(self) -> bool:
        """Enable RNDIS mode and reset modem.

        RNDIS creates usb0 interface - easiest plug-and-play mode.
        Returns True if successful.
        """
        return self.set_usb_mode(9011)

    def enable_qmi_mode(self) -> bool:
        """Enable QMI mode and reset modem.

        QMI creates wwan0 interface - modern protocol, best for ModemManager.
        Returns True if successful.
        """
        return self.set_usb_mode(9001)

    def enable_ppp_mode(self) -> bool:
        """Enable PPP mode and reset modem.

        PPP creates ppp0 interface - traditional dial-up style.
        Returns True if successful.
        """
        return self.set_usb_mode(9003)
