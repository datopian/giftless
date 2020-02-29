"""Test common transfer module functionality
"""
import pytest

from giftless import transfer


@pytest.mark.parametrize('register,requested,expected', [
    (['basic'], ['basic'], 'basic'),
    (['foobar', 'basic', 'bizbaz'], ['basic'], 'basic'),
    (['foobar', 'basic', 'bizbaz'], ['foobar'], 'foobar'),
    (['foobar', 'basic', 'bizbaz'], ['bizbaz', 'basic'], 'bizbaz'),
])
@pytest.mark.usefixtures('reset_registered_transfers')
def test_transfer_adapter_matching(register, requested, expected):
    for adapter in register:
        transfer.register_adapter(adapter, transfer.TransferAdapter())
    actual = transfer.match_transfer_adapter(requested)
    assert expected == actual[0]
    assert isinstance(actual[1], transfer.TransferAdapter)


def test_transfer_adapter_matching_nomatch():
    for adapter in ['foobar', 'basic', 'bizbaz']:
        transfer.register_adapter(adapter, transfer.TransferAdapter())
    with pytest.raises(ValueError):
        transfer.match_transfer_adapter(['complex', 'even-better'])
