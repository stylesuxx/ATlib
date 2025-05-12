# ATlib
Python library for sending and receiving SMS texts using AT commands. Higher and lower level features supported. Tested with SIM800L.

The API is relatively straightforward. The API is not asynchronous meaning all methods return the result directly.
Take a look at [the source](/src/atlib) for the full library.

For an application of this library, see [gsm-agent](https://github.com/swordstrike1/gsm-agent). Where SMS messages can
used to run shell scripts on a server (with security checks & registration).

## Installation

The package can be installed via PIP:

```
pip install atlib
```

## API

The API features two classes for interfacing with the GSM modem.

The low level is the AT_Device class.
This class exposes only a synchronous API for sending AT commands and reading responses. It abstracts
the painful process of AT commands not directly responding due to latency. Responses are detected by a
terminated OK or ERROR string. The `read()` commands returns a tokenized list of the reply for easy parsing.
- Opening serial connection.
- Synchronizing baudrate using `sync_baudrate()` (by sending "AT" and awaiting response).
- Sending AT commands.
- Reading AT commands reliably.
- Detecting errors.

The high level is the `GSM_Device` class. This class inherits from `AT_Device`.
This class provides higher level features such as
- Unlocking the device sim using pin.
- Sending text messages.
- Reading text messages (by category unread, all, read, etc).
- Deleting text messages
- Checking device details, like manufacturer, model, serial number, ICCID, etc.
- Checking operator details
- Selecting operator
- Calling
- Checking signal strength

`GSM_Device` should only contain commands supported by all chips, if there are more special commands, they will be added to a custom class for that chip.

Currently the following Chips have additional functionality added:
- `AIR780EU`

## Supported Devices
Supported devices and functionality. Please keep in mind that the functionality depends on the breakout board you are using. For example SIM900 supports calls, but not all boards are equipped with audio jacks, so make sure that the actual hardware you need is required on the board.

Also keep in mind that not all generations of wireless communications are supported in all regions. In Europe some carriers have switched off 3G, although 2G still being widely available. 4G and 5G being the standard. So when deciding for a wireless communciation technology, make sure that your provider is still supporting it.


| Chip     | Calls | SMS | 2G | 3G | 4G  | 5G | GPS |
|----------|-------|-----|----|----|-----|----|-----|
| SIM900   | Yes   | Yes | Yes| -- | --  | -- | --  |
| SIM7070X | Yes   | Yes | Yes| -- | --  | -- | --  |
| AIR780EU | --    | Yes | -- | -- | Yes | -- | --  |



## Contributing

If you have problems with your modem, you can open issues here. I have tested all commands with a properly hooked up SIM800L on a Raspberry Pi Bullseye. Know that not all devices support all AT commands, and therefore may fail when using this library. However most devices should support the basics.

## Examples

Some examples can be found in the [/examples](/examples) directory. Refer to the library itself to see many AT commands in action already (e.g sending commands, checking responses). See below for a minimal texting application:

```python
#!/bin/python
# Console SMS sender using ATlib.

from atlib import *

# Show debug logs
import logging
logging.basicConfig(level=logging.DEBUG)

gsm = GSM_Device("/dev/serial0")
if gsm.get_sim_status() != Status.OK:
    pin = input("SIM Pin: ")
    gsm.unlock_sim(pin)
else:
    print("SIM already unlocked.")

while True:
    print("")
    nr = input("Phone number: ")
    msg = input("Message: ")

    if gsm.send_sms(nr, msg) != OK:
        print("Error sending message.")
```

## Development

### Distribution
To build and upload to pypi, first update version in  `__init__.py` and the `pyproject.toml` then run run:

```
python -m build
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

### Heritage
This code was initially developed by [arceryz](https://github.com/arceryz). He not longer maintains it and [did not have interest to publish it to pypi](https://github.com/arceryz/ATlib/issues/1) but gave me permission to continue development and publish it to pypi myself.
