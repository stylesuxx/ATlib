from typing import NamedTuple


class SignalQualityInfo(NamedTuple):
    rsrp: int
    rsrq: int


class CellInfo(NamedTuple):
    mcc: int
    mnc: int
    imsi: int
    roaming_status: int
    band: int
    bandwidth_index: int
    earfcn: int
    cell_id: int
    rsrp: int
    rsrq: int
    tac: int
    signal_level: int
    pcid: int


class Context(NamedTuple):
    id: int
    type: str
    apn: str
    value: str


class Address(NamedTuple):
    id: int
    ip: str
