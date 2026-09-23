
from atlib.GSM_Device import GSM_Device
from atlib.named_tuples import Address, Context, SignalQualityInfo


class LTE_Device(GSM_Device):
    def __init__(self, path: str, baudrate: int = 115200):
        super().__init__(path, baudrate)

    def get_signal_quality(self) -> SignalQualityInfo:
        fields = self.command("AT+CESQ").raise_for_status().fields("+CESQ")
        # The first four fields are the 2G and 3G measurements.
        rsrq, rsrp = fields[4:6]

        return SignalQualityInfo(rsrq=int(rsrq), rsrp=int(rsrp))

    def get_contexts(self) -> list[Context]:
        rows = self.command("AT+CGDCONT?").raise_for_status().rows("+CGDCONT")

        contexts: list[Context] = []
        for fields in rows:
            # Context id, PDP type, APN and address. A short answer leaves
            # the trailing fields empty.
            context_id, pdp_type, apn, address = (fields + [""] * 4)[:4]
            contexts.append(Context(int(context_id), pdp_type, apn, address))

        return contexts

    def get_addresses(self) -> list[Address]:
        rows = self.command("AT+CGPADDR").raise_for_status().rows("+CGPADDR")

        addresses: list[Address] = []
        for fields in rows:
            ip = fields[1] if len(fields) >= 2 else None
            addresses.append(Address(int(fields[0]), ip))

        return addresses

    def delete_context(self, id: int):
        self.write(f"AT+CGDCONT={id}")

        return self.read_status()

    def set_context(self, id: int, type: str, apn: str = ""):
        self.write(f"AT+CGDCONT={id},{type},{apn}")

        return self.read_status()

    def activate_context(self, id: int):
        """ Radio needs to be activated before context can be activated """
        self.write(f"AT+CGACT=1,{id}")

        return self.read_status()
