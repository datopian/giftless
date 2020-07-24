"""Storage related errors
"""
from typing import Optional


class StorageError(RuntimeError):
    """Base class for storage errors
    """
    code: Optional[int] = None

    def as_dict(self):
        return {"message": str(self),
                "code": self.code}


class ObjectNotFound(StorageError):
    code = 404


class InvalidObject(StorageError):
    code = 422
