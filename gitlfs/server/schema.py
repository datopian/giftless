"""Schema for Git LFS APIs
"""
from enum import Enum

from flask_marshmallow import Marshmallow  # type: ignore
from marshmallow import fields, validate
from marshmallow_enum import EnumField

ma = Marshmallow()


class Operation(Enum):
    """Batch operations
    """
    upload = 'upload'
    download = 'download'


class RefSchema(ma.Schema):
    """ref field schema
    """
    name = fields.String(required=True)


class ObjectSchema(ma.Schema):
    """object field schema
    """
    oid = fields.String(required=True)
    size = fields.Integer(required=True, validate=validate.Range(min=0))


class BatchRequest(ma.Schema):

    operation = EnumField(Operation, required=True)
    transfers = fields.List(fields.String, required=False, missing=['basic'])
    ref = fields.Nested(RefSchema, required=False)
    objects = fields.Nested(ObjectSchema, validate=validate.Length(min=1), many=True)


batch_request_schema = BatchRequest()
