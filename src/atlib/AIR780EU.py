
from atlib.LTE_Device import LTE_Device
from atlib.named_tuples import CellInfo
from atlib.Response import Response

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
    134217728: 28,
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
        # +CCED:LTE current cell info:232,1,...
        value = self.command("AT+CCED=0,1", timeout=30).raise_for_status().value("+CCED")
        fields = list(map(int, Response.split_fields(value.split(":", 1)[1])))

        return CellInfo(*fields)

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
        # The +NITZ URC that follows lands in the inbox for await_urc("+NITZ").
        self.command(cmd).raise_for_status()

    def get_allowed_bands(self) -> list[int]:
        # *BAND:5,0,0,0,134742213
        fields = list(map(int, self.command("AT*BAND?").raise_for_status().fields("*BAND")))
        bitmask_tdd = fields[3]
        bitmask_fdd = fields[4]

        fdd_bands = [band for mask, band in FDD_BAND_MAP.items() if bitmask_fdd & mask]
        tdd_bands = [band for mask, band in TDD_BAND_MAP.items() if bitmask_tdd & mask]

        return sorted(fdd_bands + tdd_bands)

    def get_active_band(self) -> int:
        # *BANDIND: 0, 3, 7
        fields = self.command("AT*BANDIND?").raise_for_status().fields("*BANDIND")

        return int(fields[1])

    def get_version(self) -> str:
        return self.command("AT+VER").raise_for_status().value("+VER")
