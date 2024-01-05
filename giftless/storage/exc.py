"""Storage related errors."""


class StorageError(RuntimeError):
    """Base class for storage errors."""

    code: int | None = None

    def as_dict(self) -> dict[str, str | int | None]:
        return {"message": str(self), "code": self.code}


class ObjectNotFoundError(StorageError):
    """No such object exists."""

    code = 404


class InvalidObjectError(StorageError):
    """Request is syntactically OK, but invalid (wrong fields, usually)."""

    code = 422
