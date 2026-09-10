import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.parser import parse_bank

EXAMPLE_BANK_PATH = Path(__file__).resolve().parent.parent / "example-resume-bank.md"
MINI_BANK_PATH = Path(__file__).resolve().parent / "fixtures" / "mini-bank.md"


@pytest.fixture(scope="session")
def example_bank():
    """The repo's shipped example bank — a fully-worked, fictional bank that
    exercises every rule in BANK_FORMAT.md (aliases, all four conditional
    grammar forms, education detection, Education-above-Experience)."""
    return parse_bank(EXAMPLE_BANK_PATH)


@pytest.fixture(scope="session")
def mini_bank():
    """An even smaller, unrelated bank (different entity names, module
    names, bullet ID prefixes) — proves the parser/assembler are generic,
    not hardcoded to example_bank's specific content either."""
    return parse_bank(MINI_BANK_PATH)
