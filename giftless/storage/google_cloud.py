import base64
import io
import json
import os
from datetime import timedelta
from typing import Any, BinaryIO, Dict, Optional

from google.cloud import storage  # type: ignore
from google.oauth2 import service_account  # type: ignore

from giftless.storage import ExternalStorage, StreamingStorage

from .exc import ObjectNotFound


class GoogleCloudStorage(StreamingStorage, ExternalStorage):
    """Google Cloud Storage backend supporting direct-to-cloud
    transfers.
    """

    def __init__(self, project_name: str, bucket_name: str, account_key_file: Optional[str] = None,
                 account_key_base64: Optional[str] = None, path_prefix: Optional[str] = None, **_):
        self.bucket_name = bucket_name
        self.path_prefix = path_prefix
        self.credentials = self._load_credentials(account_key_file, account_key_base64)
        self.storage_client = storage.Client(project=project_name, credentials=self.credentials)

    def get(self, prefix: str, oid: str) -> BinaryIO:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.get_blob(self._get_blob_path(prefix, oid))
        if blob is None:
            raise ObjectNotFound('Object does not exist')
        stream = io.BytesIO()
        blob.download_to_file(stream)
        stream.seek(0)
        return stream

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        blob.upload_from_file(data_stream)
        return data_stream.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        return blob.exists()  # type: ignore

    def get_size(self, prefix: str, oid: str) -> int:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.get_blob(self._get_blob_path(prefix, oid))
        if blob is None:
            raise ObjectNotFound("Object does not exist")
        return blob.size  # type: ignore

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(prefix, oid, http_method='PUT', expires_in=expires_in),
                    "header": {},
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filename = extra.get('filename') if extra else None
        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(prefix, oid, expires_in=expires_in, filename=filename),
                    "header": {},
                    "expires_in": expires_in
                }
            }
        }

    def _get_blob_path(self, prefix: str, oid: str) -> str:
        """Get the path to a blob in storage
        """
        if not self.path_prefix:
            storage_prefix = ''
        elif self.path_prefix[0] == '/':
            storage_prefix = self.path_prefix[1:]
        else:
            storage_prefix = self.path_prefix
        return os.path.join(storage_prefix, prefix, oid)

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int, http_method: str = 'GET',
                        filename: Optional[str] = None) -> str:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        disposition = f'attachment; filename={filename}' if filename else None
        url: str = blob.generate_signed_url(expiration=timedelta(seconds=expires_in), method=http_method, version='v4',
                                            response_disposition=disposition, credentials=self.credentials)
        return url

    @staticmethod
    def _load_credentials(account_key_file: Optional[str], account_key_base64: Optional[str]) \
            -> service_account.Credentials:
        """Load Google Cloud credentials from passed configuration
        """
        if account_key_file and account_key_base64:
            raise ValueError('Provide either account_key_file or account_key_base64 but not both')
        elif account_key_file:
            return service_account.Credentials.from_service_account_file(account_key_file)
        elif account_key_base64:
            account_info = json.loads(base64.b64decode(account_key_base64))
            return service_account.Credentials.from_service_account_info(account_info)
        else:
            raise ValueError('You must provide either account_key_file or account_key_base64')
