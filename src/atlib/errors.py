class ATError(Exception):
    """ Base class for a failed AT command. """


class ATTimeout(ATError):
    """ The device sent no final result code within the read timeout. """


class ATCommandError(ATError):
    """ The device answered with a plain ERROR. """


class CMEError(ATCommandError):
    """ The device answered with +CME ERROR (3GPP TS 27.007, section 9). """

    def __init__(self, code: int | None, message: str = ""):
        super().__init__(f"+CME ERROR: {message or code}")
        self.code = code
        self.message = message


class CMSError(ATCommandError):
    """ The device answered with +CMS ERROR (3GPP TS 27.005, section 3.2.5). """

    def __init__(self, code: int | None, message: str = ""):
        super().__init__(f"+CMS ERROR: {message or code}")
        self.code = code
        self.message = message
