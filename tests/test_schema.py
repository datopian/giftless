"""Tests for schema definitions
"""

import pytest
from marshmallow import ValidationError

from gitlfs.server import schema


def _batch_request_payload(delete_keys=(), **kwargs):
    """Generate sample batch request payload
    """
    payload = {
        "operation": "download",
        "transfers": ["basic"],
        "ref": {"name": "refs/heads/master"},
        "objects": [
            {
                "oid": "12345678",
                "size": 123
            }
        ]
    }

    for key in delete_keys:
        del payload[key]

    payload.update(kwargs)
    return payload


@pytest.mark.parametrize('input', [
    (_batch_request_payload()),
    (_batch_request_payload(operation='upload')),
    (_batch_request_payload(delete_keys=['ref', 'transfers'])),
])
def test_batch_request_schema_valid(input):
    parsed = schema.BatchRequest().load(input)
    assert parsed


@pytest.mark.parametrize('input', [
    ({}),
    (_batch_request_payload(operation='sneeze')),
    (_batch_request_payload(objects=[])),
    (_batch_request_payload(objects=[{"oid": 123456, "size": "large of course"}])),
    (_batch_request_payload(objects=[{"oid": "123abc", "size": -12}])),
])
def test_batch_request_schema_invalid(input):
    with pytest.raises(ValidationError):
        schema.BatchRequest().load(input)


def test_batch_request_default_transfer():
    input = _batch_request_payload(delete_keys=['transfers'])
    parsed = schema.BatchRequest().load(input)
    assert ['basic'] == parsed['transfers']
