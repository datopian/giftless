"""Tests for schema definitions
"""

import pytest
from marshmallow import ValidationError

from giftless import schema

from .helpers import batch_request_payload


@pytest.mark.parametrize('input', [
    (batch_request_payload()),
    (batch_request_payload(operation='upload')),
    (batch_request_payload(delete_keys=['ref', 'transfers'])),
])
def test_batch_request_schema_valid(input):
    parsed = schema.BatchRequest().load(input)
    assert parsed


@pytest.mark.parametrize('input', [
    ({}),
    (batch_request_payload(operation='sneeze')),
    (batch_request_payload(objects=[])),
    (batch_request_payload(objects=[{"oid": 123456, "size": "large of course"}])),
    (batch_request_payload(objects=[{"oid": "123abc", "size": -12}])),
])
def test_batch_request_schema_invalid(input):
    with pytest.raises(ValidationError):
        schema.BatchRequest().load(input)


def test_batch_request_default_transfer():
    input = batch_request_payload(delete_keys=['transfers'])
    parsed = schema.BatchRequest().load(input)
    assert ['basic'] == parsed['transfers']


def test_object_schema_accepts_x_fields():
    payload = {"oid": "123abc", "size": 1212, "x-filename": "foobarbaz", "x-mtime": 123123123123}
    parsed = schema.ObjectSchema().load(payload)
    assert "foobarbaz" == parsed['extra']['filename']
    assert 123123123123 == parsed['extra']['mtime']
    assert "123abc" == parsed['oid']


def test_object_schema_rejects_unknown_fields():
    payload = {"oid": "123abc", "size": 1212, "x-filename": "foobarbaz", "more": "stuff"}
    with pytest.raises(ValidationError):
        schema.ObjectSchema().load(payload)
