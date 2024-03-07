"""Schema for Git LFS APIs."""
from enum import Enum
from typing import Any

import marshmallow
from flask_marshmallow import Marshmallow
from marshmallow import fields, pre_load, validate

ma = Marshmallow()

# TODO @athornton: probably a big job but it feels like this is what Pydantic
# is for.


class Operation(Enum):
    """Batch operations."""

    upload = "upload"
    download = "download"


class RefSchema(ma.Schema):  # type:ignore[name-defined]
    """ref field schema."""

    name = fields.String(required=True)


class ObjectSchema(ma.Schema):  # type:ignore[name-defined]
    """object field schema."""

    oid = fields.String(required=True)
    size = fields.Integer(required=True, validate=validate.Range(min=0))

    extra = fields.Dict(required=False, load_default=dict)

    @pre_load
    def set_extra_fields(
        self, data: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        extra = {}
        rest = {}
        for k, v in data.items():
            if k.startswith("x-"):
                extra[k[2:]] = v
            else:
                rest[k] = v
        return {"extra": extra, **rest}


class BatchRequest(ma.Schema):  # type:ignore[name-defined]
    """batch request schema."""

    operation = fields.Enum(Operation, required=True)
    transfers = fields.List(
        fields.String, required=False, load_default=["basic"]
    )
    ref = fields.Nested(RefSchema, required=False)
    objects = fields.Nested(
        ObjectSchema, validate=validate.Length(min=1), many=True, required=True
    )


batch_request_schema = BatchRequest(unknown=marshmallow.EXCLUDE)
