from atlib.GSM_Device import GSM_Device
from atlib.named_tuples import Context


class LTE_Device(GSM_Device):
    def __init__(self, path: str, baudrate: int = 115200):
        super().__init__(path, baudrate)

    def get_contexts(self) -> list[str]:
        self.write("AT+CGDCONT?")
        response = self.read()

        contexts = []
        for line in response:
            if line.startswith('+CGDCONT:'):
                value = line.split(":")[1].strip()
                fields = value.split(",")
                clean_fields = [int(fields[0].strip())] + [f.strip().strip('"') for f in fields[1:4]]

                while len(clean_fields) < 4:
                    clean_fields.append("")

                context = Context(*clean_fields)
                contexts.append(context)

        return contexts

    def delete_context(self, id: int):
        self.write(f"AT+CGDCONT={id}")

        return self.read_status()

    def set_context(self, id: int, type: str, apn: str = ""):
        self.write(f"AT+CGDCONT={id},{type},{apn}")

        return self.read_status()

    def activate_context(self, id: int):
        self.write(f"AT+CGACT=1,{id}")

        return self.read_status()
