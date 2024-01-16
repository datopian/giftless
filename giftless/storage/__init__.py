"""Storage base classes."""
import mimetypes
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, BinaryIO

from . import exc

# TODO @athornton: Think about refactoring this; some deduplication of
# `verify_object`, at least.


class VerifiableStorage(ABC):
    """A storage backend that supports object verification API.

    All streaming backends should be 'verifiable'.
    """

    @abstractmethod
    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Check that object exists and has the right size.

        This method should not throw an error if the object does not
        exist, but return False.
        """


class StreamingStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters."""

    @abstractmethod
    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        pass

    @abstractmethod
    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        pass

    @abstractmethod
    def exists(self, prefix: str, oid: str) -> bool:
        pass

    @abstractmethod
    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def get_mime_type(self, prefix: str, oid: str) -> str:
        return "application/octet-stream"

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Verify that an object exists and has the right size."""
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFoundError:
            return False


class ExternalStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters."""

    @abstractmethod
    def get_upload_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_download_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def exists(self, prefix: str, oid: str) -> bool:
        pass

    @abstractmethod
    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Verify that object exists and has the correct size."""
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFoundError:
            return False


class MultipartStorage(VerifiableStorage, ABC):
    """Base class for storage that supports multipart uploads."""

    @abstractmethod
    def get_multipart_actions(
        self,
        prefix: str,
        oid: str,
        size: int,
        part_size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_download_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def exists(self, prefix: str, oid: str) -> bool:
        pass

    @abstractmethod
    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Verify that object exists and has the correct size."""
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFoundError:
            return False


def guess_mime_type_from_filename(filename: str) -> str | None:
    """Based on the filename, guess what MIME type it is."""
    return mimetypes.guess_type(filename)[0]
