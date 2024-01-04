import os
import shutil
from typing import Any, BinaryIO, Optional

from flask import Flask

from giftless.storage import MultipartStorage, StreamingStorage, exc
from giftless.view import ViewProvider


class LocalStorage(StreamingStorage, MultipartStorage, ViewProvider):
    """Local storage implementation

    This storage backend  works by storing files in the local file system.
    While it can be used in production, large scale deployment will most likely
    want to use a more scalable solution such as one of the cloud storage backends.
    """

    def __init__(self, path: Optional[str] = None, **_: Any) -> None:
        if path is None:
            path = "lfs-storage"
        self.path = path
        self._create_path(self.path)

    def get(self, prefix: str, oid: str) -> BinaryIO:
        path = self._get_path(prefix, oid)
        if os.path.isfile(path):
            return open(path, "br")
        else:
            raise exc.ObjectNotFound("Object was not found")

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        path = self._get_path(prefix, oid)
        directory = os.path.dirname(path)
        self._create_path(directory)
        with open(path, "bw") as dest:
            shutil.copyfileobj(data_stream, dest)
            return dest.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        return os.path.isfile(self._get_path(prefix, oid))

    def get_size(self, prefix: str, oid: str) -> int:
        if self.exists(prefix, oid):
            return os.path.getsize(self._get_path(prefix, oid))
        raise exc.ObjectNotFound("Object was not found")

    def get_mime_type(self, prefix: str, oid: str) -> str:
        if self.exists(prefix, oid):
            return "application/octet-stream"
        raise exc.ObjectNotFound("Object was not found")

    def get_multipart_actions(
        self,
        prefix: str,
        oid: str,
        size: int,
        part_size: int,
        expires_in: int,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {}

    def get_download_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {}

    def register_views(self, app: Flask) -> None:
        super().register_views(app)

    def _get_path(self, prefix: str, oid: str) -> str:
        return os.path.join(self.path, prefix, oid)

    @staticmethod
    def _create_path(path: str) -> None:
        if not os.path.isdir(path):
            os.makedirs(path)
