import mimetypes
from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Dict, Iterable, Optional

from . import exc


class VerifiableStorage(ABC):
    """A storage backend that supports object verification API

    All streaming backends should be 'verifiable'.
    """
    @abstractmethod
    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Check that object exists and has the right size

        This method should not throw an error if the object does not exist, but return False
        """
        pass


class StreamingStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters
    """
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

    def get_mime_type(self, prefix: str, oid: str) -> Optional[str]:
        return "application/octet-stream"

    def verify_object(self, prefix: str, oid: str, size: int):
        """Verify that an object exists
        """
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFound:
            return False


class ExternalStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters
    """
    @abstractmethod
    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def exists(self, prefix: str, oid: str) -> bool:
        pass

    @abstractmethod
    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFound:
            return False


class MultipartStorage(VerifiableStorage, ABC):
    @abstractmethod
    def get_multipart_actions(self, prefix: str, oid: str, size: int, part_size: int, expires_in: int,
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def exists(self, prefix: str, oid: str) -> bool:
        pass

    @abstractmethod
    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFound:
            return False


def guess_mime_type_from_filename(filename: str) -> Optional[str]:
    return mimetypes.guess_type(filename)[0]
