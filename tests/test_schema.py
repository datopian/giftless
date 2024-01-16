"""Tests for schema definitions."""

import pytest
from marshmallow import ValidationError

from giftless import schema

from .helpers import batch_request_payload


@pytest.mark.parametrize(
    "inp",
    [
        (batch_request_payload()),
        (batch_request_payload(operation="upload")),
        (batch_request_payload(delete_keys=["ref", "transfers"])),
    ],
)
def test_batch_request_schema_valid(inp: str) -> None:
    parsed = schema.BatchRequest().load(inp)
    assert parsed


@pytest.mark.parametrize(
    "inp",
    [
        ({}),
        (batch_request_payload(operation="sneeze")),
        (batch_request_payload(objects=[])),
        (
            batch_request_payload(
                objects=[{"oid": 123456, "size": "large of course"}]
            )
        ),
        (batch_request_payload(objects=[{"oid": "123abc", "size": -12}])),
    ],
)
def test_batch_request_schema_invalid(inp: str) -> None:
    with pytest.raises(ValidationError):
        schema.BatchRequest().load(inp)


def test_batch_request_default_transfer() -> None:
    inp = batch_request_payload(delete_keys=["transfers"])
    parsed = schema.BatchRequest().load(inp)
    assert ["basic"] == parsed["transfers"]


def test_object_schema_accepts_x_fields() -> None:
    payload = {
        "oid": "123abc",
        "size": 1212,
        "x-filename": "foobarbaz",
        "x-mtime": 123123123123,
        "x-disposition": "inline",
    }
    parsed = schema.ObjectSchema().load(payload)
    assert parsed["extra"]["filename"] == "foobarbaz"
    assert parsed["extra"]["mtime"] == 123123123123
    assert parsed["oid"] == "123abc"
    assert parsed["extra"]["disposition"] == "inline"


def test_object_schema_rejects_unknown_fields() -> None:
    payload = {
        "oid": "123abc",
        "size": 1212,
        "x-filename": "foobarbaz",
        "more": "stuff",
    }
    with pytest.raises(ValidationError):
        schema.ObjectSchema().load(payload)
