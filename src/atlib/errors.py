class ATError(Exception):
    """
    Base class for a failed AT command.

    `response` is the Response the error was raised for, when one exists.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.response = None


class ATTimeout(ATError):
    """ The device sent no final result code within the read timeout. """


class ATCommandError(ATError):
    """ The device answered with a plain ERROR. """


class ATParseError(ATError):
    """ A response lacks the line the caller asked for. """


class ATDecodeError(ATError):
    """ The device sent bytes that are not valid UTF-8. """


class CMEError(ATCommandError):
    """
    The device answered with +CME ERROR (3GPP TS 27.007, section 9).

    `code` holds the numeric value when the device reports numbers (AT+CMEE=1),
    `message` holds the text when it reports verbose errors (AT+CMEE=2).
    """

    def __init__(self, code: int | None, message: str = ""):
        super().__init__(f"+CME ERROR: {message or code}")
        self.code = code
        self.message = message


class CMSError(ATCommandError):
    """
    The device answered with +CMS ERROR (3GPP TS 27.005, section 3.2.5).

    `code` and `message` follow the same rule as CMEError.
    """

    def __init__(self, code: int | None, message: str = ""):
        super().__init__(f"+CMS ERROR: {message or code}")
        self.code = code
        self.message = message
