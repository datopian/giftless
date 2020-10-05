from abc import ABC
from typing import Any, BinaryIO, Dict, Iterable, Optional

from . import exc


class VerifiableStorage(ABC):
    """A storage backend that supports object verification API

    All streaming backends should be 'verifiable'.
    """
    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Check that object exists and has the right size

        This method should not throw an error if the object does not exist, but return False
        """
        pass


class StreamingStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters
    """
    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        pass

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        pass

    def exists(self, prefix: str, oid: str) -> bool:
        pass

    def get_size(self, prefix: str, oid: str) -> int:
        pass

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
    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def exists(self, prefix: str, oid: str) -> bool:
        pass

    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFound:
            return False


class MultipartStorage(VerifiableStorage, ABC):
    def get_multipart_actions(self, prefix: str, oid: str, size: int, part_size: int, expires_in: int,
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def exists(self, prefix: str, oid: str) -> bool:
        pass

    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFound:
            return False
