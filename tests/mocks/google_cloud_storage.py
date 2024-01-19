"""Mock for google_cloud_storage that just uses a temporary directory
rather than talking to Google.  This effectively makes it a LocalStorage
implementation, of course.
"""

import shutil
from pathlib import Path
from typing import Any, BinaryIO

from giftless.storage.exc import ObjectNotFoundError
from giftless.storage.google_cloud import GoogleCloudStorage


class MockGoogleCloudStorage(GoogleCloudStorage):
    """Mocks a GoogleCloudStorage object by simulating it with a local
    directory.
    """

    def __init__(
        self,
        project_name: str,
        bucket_name: str,
        path: Path,
        account_key_file: str | None = None,
        account_key_base64: str | None = None,
        path_prefix: str | None = None,
        serviceaccount_email: str | None = None,
        **_: Any,
    ) -> None:
        super().__init__(
            project_name=project_name,
            bucket_name=bucket_name,
            account_key_file=account_key_file,
            account_key_base64=account_key_base64,
            serviceaccount_email=serviceaccount_email,
        )
        self._path = path

    def _get_blob_path(self, prefix: str, oid: str) -> str:
        return str(self._get_blob_pathlib_path(prefix, oid))

    def _get_blob_pathlib_path(self, prefix: str, oid: str) -> Path:
        return Path(self._path / Path(prefix) / oid)

    @staticmethod
    def _create_path(spath: str) -> None:
        path = Path(spath)
        if not path.is_dir():
            path.mkdir(parents=True)

    def _get_signed_url(
        self,
        prefix: str,
        oid: str,
        expires_in: int,
        http_method: str = "GET",
        filename: str | None = None,
        disposition: str | None = None,
    ) -> str:
        return f"https://example.com/signed_blob/{prefix}/{oid}"

    def get(self, prefix: str, oid: str) -> BinaryIO:
        obj = self._get_blob_pathlib_path(prefix, oid)
        if not obj.exists():
            raise ObjectNotFoundError("Object does not exist")
        return obj.open("rb")

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        path = self._get_blob_pathlib_path(prefix, oid)
        directory = path.parent
        self._create_path(str(directory))
        with path.open("bw") as dest:
            shutil.copyfileobj(data_stream, dest)
            return dest.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        return self._get_blob_pathlib_path(prefix, oid).is_file()

    def get_size(self, prefix: str, oid: str) -> int:
        if not self.exists(prefix, oid):
            raise ObjectNotFoundError("Object does not exist")
        path = self._get_blob_pathlib_path(prefix, oid)
        return path.stat().st_size
