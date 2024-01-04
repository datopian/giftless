"""Storage related errors
"""


class StorageError(RuntimeError):
    """Base class for storage errors"""

    code: int | None = None

    def as_dict(self) -> dict[str, str | int | None]:
        return {"message": str(self), "code": self.code}


class ObjectNotFound(StorageError):
    code = 404


class InvalidObject(StorageError):
    code = 422
