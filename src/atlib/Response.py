import csv
import typing

from .errors import ATCommandError, ATError, ATParseError, ATTimeout, CMEError, CMSError
from .Status import Status


class Response:
    """
    One parsed answer to an AT command, built from the tokens AT_Device.read()
    returns.

    `echo` is the echoed command when the device sent one, `lines` the
    information lines, `final` the raw final result code, `status` its
    Status constant and `error` the exception matching a failed result.
    A URC arriving after the final result code stays in `lines`.
    """

    FINAL_RESULT_CODES = (Status.OK, Status.ERROR, Status.PROMPT, Status.TIMEOUT)
    VERBOSE_ERROR_PREFIXES = ("+CME ERROR", "+CMS ERROR")

    def __init__(self, tokens: typing.Sequence[str], command: str = ""):
        self.tokens = list(tokens)
        self.command = command

        tokens = list(tokens)
        self.echo: str | None = None
        if tokens and tokens[0] == command:
            self.echo = tokens.pop(0)

        final_index = self._final_index(tokens)
        if final_index is None:
            self.final = ""
            self.lines = tokens
        else:
            self.final = tokens[final_index]
            self.lines = tokens[:final_index] + tokens[final_index + 1:]

        self.status = self._status_for(self.final)
        self.error = self._error_for(self.final)
        if self.error is not None:
            self.error.response = self

    @property
    def is_ok(self) -> bool:
        return self.status == Status.OK

    def raise_for_status(self) -> "Response":
        """ Raise the response's error, or return the response itself. """
        if self.error is not None:
            raise self.error

        return self

    def line(self, prefix: str = "") -> str:
        """
        The first information line starting with prefix.

        Without a prefix this is the first information line, which is how a
        device answers commands like AT+CGSN that carry no prefix.
        """
        for candidate in self.lines:
            if candidate.startswith(prefix):
                return candidate

        raise ATParseError(f"no {prefix or 'information'} line in the answer to {self.command}")

    def value(self, prefix: str = "") -> str:
        """
        The payload of the prefixed line, with the prefix, its colon, and
        surrounding quotes and whitespace removed.

        A device may answer with a bare line instead of a prefixed one
        (AT+CGMI on SIM800 and SIM7600), so a missing prefix falls back to the
        first information line.
        """
        try:
            line = self.line(prefix)
        except ATParseError:
            if not prefix:
                raise

            line = self.line()

        if prefix and line.startswith(prefix):
            line = line[len(prefix):]
            if ":" in line:
                line = line.split(":", 1)[1]

        return line.strip().strip('"')

    def fields(self, prefix: str = "") -> list[str]:
        """ The comma separated fields of the prefixed line, quotes removed. """
        return self.split_fields(self.value(prefix))

    def rows(self, prefix: str) -> list[list[str]]:
        """ The fields of every line starting with prefix, one list per line. """
        payloads = [line[len(prefix):].split(":", 1)[-1] for line in self.lines if line.startswith(prefix)]
        return [self.split_fields(payload.strip()) for payload in payloads]

    @staticmethod
    def split_fields(payload: str) -> list[str]:
        """ Split a comma separated AT payload, honouring quoted fields. """
        payload = payload.strip()
        if payload == "":
            return []

        return [field.strip() for field in next(csv.reader([payload], skipinitialspace=True))]

    @classmethod
    def _final_index(cls, tokens: list[str]) -> int | None:
        for i in range(len(tokens) - 1, -1, -1):
            if cls._is_final(tokens[i]):
                return i

        return None

    @classmethod
    def _is_final(cls, token: str) -> bool:
        return token in cls.FINAL_RESULT_CODES or token.startswith(cls.VERBOSE_ERROR_PREFIXES)

    @classmethod
    def _status_for(cls, final: str) -> str:
        match final:
            case Status.OK | Status.ERROR | Status.PROMPT | Status.TIMEOUT:
                return final
            case _ if final.startswith(cls.VERBOSE_ERROR_PREFIXES):
                return Status.ERROR
            case _:
                return Status.UNKNOWN

    def _error_for(self, final: str) -> ATError | None:
        match final:
            case Status.OK | Status.PROMPT:
                return None
            case Status.ERROR:
                return ATCommandError(f"{self.command} answered ERROR")
            case Status.TIMEOUT:
                return ATTimeout(f"{self.command} sent no final result code")
            case _ if final.startswith("+CME ERROR"):
                return CMEError(*self._verbose_error(final))
            case _ if final.startswith("+CMS ERROR"):
                return CMSError(*self._verbose_error(final))
            case _:
                return ATError(f"{self.command} answered without a final result code")

    @staticmethod
    def _verbose_error(final: str) -> tuple[int | None, str]:
        """ Split "+CME ERROR: 10" into (10, "") and "+CME ERROR: text" into (None, "text"). """
        detail = final.split(":", 1)[1].strip() if ":" in final else ""
        if detail.isdigit():
            return (int(detail), "")

        return (None, detail)
