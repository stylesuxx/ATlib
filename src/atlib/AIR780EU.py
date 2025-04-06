from atlib.GSM_Device import GSM_Device
from atlib.named_tuples import SignalQualityInfo, CellInfo


class AIR780EU(GSM_Device):
    """
    Based on ASR160x chipset.

    This module has a very reduce/locked AT command set. It is preconfigured to
    use LTE and might? fall back to GSM, which I could personally not reproduce.
    So for the time being, we are going to assume that it is always in LTE mode.
    """
    def __init__(self, path: str, baudrate: int = 9600):
        super().__init__(path, baudrate)

    def get_cell_info(self) -> CellInfo:
        """Quering cell info can take some time."""
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
