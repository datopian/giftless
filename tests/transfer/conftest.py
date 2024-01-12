"""Some global fixtures for transfer tests
"""
from typing import Generator

import pytest

from giftless import transfer


@pytest.fixture
def reset_registered_transfers() -> Generator:
    """Reset global registered transfer adapters for each module"""
    adapters = dict(transfer._registered_adapters)
    try:
        yield
    finally:
        transfer._registered_adapters = adapters
