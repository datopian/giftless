"""Local storage implementation, for development/testing or small-scale
deployments.
"""
import shutil
from pathlib import Path
from typing import Any, BinaryIO

from flask import Flask

from giftless.storage import MultipartStorage, StreamingStorage, exc
from giftless.view import ViewProvider


class LocalStorage(StreamingStorage, MultipartStorage, ViewProvider):
    """Local storage implementation.

    This storage backend works by storing files in the local file
    system.  While it can be used in production, large scale
    deployment will most likely want to use a more scalable solution
    such as one of the cloud storage backends.
    """

    def __init__(self, path: str | None = None, **_: Any) -> None:
        if path is None:
            path = "lfs-storage"
        self.path = path
        self._create_path(self.path)

    def get(self, prefix: str, oid: str) -> BinaryIO:
        path = self._get_path(prefix, oid)
        if path.is_file():
            return path.open("br")
        else:
            raise exc.ObjectNotFoundError(f"Object {path} was not found")

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        path = self._get_path(prefix, oid)
        directory = path.parent
        self._create_path(str(directory))
        with path.open("bw") as dest:
            shutil.copyfileobj(data_stream, dest)
            return dest.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        path = self._get_path(prefix, oid)
        return path.is_file()

    def get_size(self, prefix: str, oid: str) -> int:
        if self.exists(prefix, oid):
            path = self._get_path(prefix, oid)
            return path.stat().st_size
        raise exc.ObjectNotFoundError("Object was not found")

    def get_mime_type(self, prefix: str, oid: str) -> str:
        if self.exists(prefix, oid):
            return "application/octet-stream"
        raise exc.ObjectNotFoundError("Object was not found")

    def get_multipart_actions(
        self,
        prefix: str,
        oid: str,
        size: int,
        part_size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {}

    def get_download_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {}

    def register_views(self, app: Flask) -> None:
        super().register_views(app)

    def _get_path(self, prefix: str, oid: str) -> Path:
        return Path(self.path) / prefix / oid

    @staticmethod
    def _create_path(spath: str) -> None:
        path = Path(spath)
        if not path.is_dir():
            path.mkdir(parents=True)
