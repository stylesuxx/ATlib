from atlib import LTE_Device
from atlib.named_tuples import SignalQualityInfo, CellInfo

# According to AT manual for this modem. The actually working channels depend on
# the region the modem is supporting, so TDD Bands will for example not work on
# the EU version of the modem.
FDD_BAND_MAP = {
    1: 1,
    # 2: 2,  # ???
    4: 3,
    8: 4,
    16: 5,
    # 32: 6,  # ???
    64: 7,
    128: 8,  # Undocumented but confirmed
    65536: 17,
    524288: 20,
    268435456: 28,
}

TDD_BAND_MAP = {
    2: 34,
    32: 38,
    64: 39,
    128: 40,
    256: 41,
}


class AIR780EU(LTE_Device):
    """
    Based on ASR160x chipset.

    This module has a very reduce/locked AT command set. It is preconfigured to
    use LTE and might? fall back to GSM, which I could personally not reproduce.
    So for the time being, we are going to assume that it is always in LTE mode.
    """
    def __init__(self, path: str, baudrate: int = 115200):
        super().__init__(path, baudrate)

    def get_cell_info(self) -> CellInfo:
        """Querying cell info can take some time."""
        self.write("AT+CCED=0,1")
        response = self.read(30)
        value = response[1].split(":")[2].strip().replace("\"", "")
        fields = list(map(int, value.split(",")))

        return CellInfo(*fields)

    def get_signal_quality(self) -> SignalQualityInfo:
        self.write("AT+CESQ")
        response = self.read()
        value = response[1].split(":")[1].strip().replace("\"", "")
        fields = list(map(int, value.split(",")))
        na1, na2, na3, na4, rsrq, rsrp = fields

        return SignalQualityInfo(rsrq=int(rsrq), rsrp=int(rsrp))

    def set_allowed_bands(
        self,
        bands: list[int],
        roaming: int = 1,
        srv_domain: int = 1,
        band_priority_flag: int = 0
    ) -> None:
        fdd_mask = sum(mask for mask, band in FDD_BAND_MAP.items() if band in bands)
        tdd_mask = sum(mask for mask, band in TDD_BAND_MAP.items() if band in bands)

        cmd = f"AT*BAND=5,0,0,{tdd_mask},{fdd_mask},{roaming},{srv_domain},{band_priority_flag}"
        self.write(cmd)
        self.read(10, "+NITZ")

    def get_allowed_bands(self) -> list[int]:
        self.write("AT*BAND?")
        response = self.read()
        # *BAND:5,0,0,0,134742213
        value = response[1].split(":")[1].strip()
        fields = list(map(int, value.split(",")))
        bitmask_tdd = fields[3]
        bitmask_fdd = fields[4]

        fdd_bands = [band for mask, band in FDD_BAND_MAP.items() if bitmask_fdd & mask]
        tdd_bands = [band for mask, band in TDD_BAND_MAP.items() if bitmask_tdd & mask]

        return sorted(fdd_bands + tdd_bands)

    def get_active_band(self) -> list[int]:
        self.write("AT*BANDIND?")
        response = self.read()
        # *BANDIND: 0, 3, 7
        value = response[1].split(":")[1].strip()
        fields = list(map(int, value.split(",")))
        band = fields[1]

        return band
