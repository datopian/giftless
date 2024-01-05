"""Some useful type definitions for transfer protocols."""
from typing import Any, TypedDict


class ObjectAttributes(TypedDict):
    """Type for object attributes sent in batch request."""

    oid: str
    size: int


class BasicUploadActions(TypedDict, total=False):
    """Fundamental actions for upload."""

    upload: dict[str, Any]
    verify: dict[str, Any]


class UploadObjectAttributes(ObjectAttributes, total=False):
    """Convert BasicUploadActions to object attributes."""

    actions: BasicUploadActions


class MultipartUploadActions(TypedDict, total=False):
    """Additional actions to support multipart uploads."""

    init: dict[str, Any]
    commit: dict[str, Any]
    parts: list[dict[str, Any]]
    abort: dict[str, Any]
    verify: dict[str, Any]


class MultipartUploadObjectAttributes(ObjectAttributes, total=False):
    """Convert MultipartUploadActions to object attributes."""

    actions: MultipartUploadActions
