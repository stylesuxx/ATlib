class Operator:
    def __init__(self, stat: int, long: str, short: str, numeric: int,
                 access_technologies: int = None):
        self.stat = stat
        self.long = long
        self.short = short
        self.numeric = numeric
        self.access_technologies = access_technologies

    def get_stat(self) -> int:
        return self.stat

    def get_long(self) -> str:
        return self.long

    def get_short(self) -> str:
        return self.short

    def get_numeric(self) -> int:
        return self.numeric

    def get_access_technologies(self) -> int:
        return self.access_technologies

    def __repr__(self):
        return f"({self.stat}, {self.long}, {self.short}, {self.numeric}, {self.access_technologies})"
