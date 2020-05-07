"""Schema for Git LFS APIs
"""
from enum import Enum

from flask_marshmallow import Marshmallow  # type: ignore
from marshmallow import fields, pre_load, validate
from marshmallow_enum import EnumField

ma = Marshmallow()


class Operation(Enum):
    """Batch operations
    """
    upload = 'upload'
    download = 'download'


class RefSchema(ma.Schema):  # type: ignore
    """ref field schema
    """
    name = fields.String(required=True)


class ObjectSchema(ma.Schema):  # type: ignore
    """object field schema
    """
    oid = fields.String(required=True)
    size = fields.Integer(required=True, validate=validate.Range(min=0))

    extra = fields.Dict(required=False, missing=dict)

    @pre_load
    def set_extra_fields(self, data, **_):
        extra = {}
        rest = {}
        for k, v in data.items():
            if k.startswith('x-'):
                extra[k[2:]] = v
            else:
                rest[k] = v
        return {'extra': extra, **rest}


class BatchRequest(ma.Schema):  # type: ignore

    operation = EnumField(Operation, required=True)
    transfers = fields.List(fields.String, required=False, missing=['basic'])
    ref = fields.Nested(RefSchema, required=False)
    objects = fields.Nested(ObjectSchema, validate=validate.Length(min=1), many=True, required=True)


batch_request_schema = BatchRequest()
