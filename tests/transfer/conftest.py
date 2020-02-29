"""Some global fixtures for transfer tests
"""
import pytest

from giftless import transfer


@pytest.fixture()
def reset_registered_transfers():
    """Reset global registered transfer adapters for each module
    """
    adapters = dict(transfer._registered_adapters)  # noqa
    try:
        yield
    finally:
        transfer._registered_adapters = adapters  # noqa
