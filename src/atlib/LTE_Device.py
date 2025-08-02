from atlib.GSM_Device import GSM_Device
from atlib.named_tuples import Context, Address


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

    def get_addresses(self) -> list[str]:
        self.write("AT+CGPADDR")
        response = self.read()

        addresses = []
        for line in response:
            if line.startswith('+CGPADDR:'):
                value = line.split(":", 1)[1].strip()
                fields = [f.strip() for f in value.split(",")]
                id = int(fields[0])
                ip = None
                if len(fields) >= 2:
                    ip = fields[1].strip('"')

                addresses.append(Address(id, ip))

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
