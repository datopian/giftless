"""Some useful type definitions for transfer protocols
"""
import sys
from typing import Any, Dict, List

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class ObjectAttributes(TypedDict):
    """Type for object attributes sent in batch request
    """
    oid: str
    size: int


class BasicUploadActions(TypedDict, total=False):
    upload: Dict[str, Any]
    verify: Dict[str, Any]


class UploadObjectAttributes(ObjectAttributes, total=False):
    actions: BasicUploadActions


class MultipartUploadActions(TypedDict, total=False):
    init: Dict[str, Any]
    commit: Dict[str, Any]
    parts: List[Dict[str, Any]]
    abort: Dict[str, Any]
    verify: Dict[str, Any]


class MultipartUploadObjectAttributes(ObjectAttributes, total=False):
    actions: MultipartUploadActions
