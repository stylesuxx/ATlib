import importlib
import re
from pathlib import Path

import pytest

import atlib
from atlib.GSM_Device import GSM_Device


@pytest.mark.parametrize("name", ["AIR780EU", "SIM7070X", "SIM7600GH"])
def test_chip_modules_import_through_the_package(name):
    module = importlib.import_module(f"atlib.{name}")

    assert issubclass(getattr(module, name), GSM_Device)
    assert getattr(atlib, name) is getattr(module, name)


def test_package_version_matches_pyproject():
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)

    assert atlib.__version__ == declared
