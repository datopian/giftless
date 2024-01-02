"""Some useful type definitions for transfer protocols
"""
import sys
from typing import Any

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class ObjectAttributes(TypedDict):
    """Type for object attributes sent in batch request"""

    oid: str
    size: int


class BasicUploadActions(TypedDict, total=False):
    upload: dict[str, Any]
    verify: dict[str, Any]


class UploadObjectAttributes(ObjectAttributes, total=False):
    actions: BasicUploadActions


class MultipartUploadActions(TypedDict, total=False):
    init: dict[str, Any]
    commit: dict[str, Any]
    parts: list[dict[str, Any]]
    abort: dict[str, Any]
    verify: dict[str, Any]


class MultipartUploadObjectAttributes(ObjectAttributes, total=False):
    actions: MultipartUploadActions
