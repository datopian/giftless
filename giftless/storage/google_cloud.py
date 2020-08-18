import json
import os
from datetime import timedelta
from typing import Any, BinaryIO, Dict, Optional
from urllib.parse import quote

from google.cloud import storage  # type: ignore
from google.oauth2 import service_account  # type: ignore

from giftless.storage import ExternalStorage, StreamingStorage

from .exc import ObjectNotFound


class GoogleCloudBlobStorage(StreamingStorage, ExternalStorage):
    """Google Cloud Storage backend supporting direct-to-cloud
    transfers.
    """

    def __init__(self, project_name: str, bucket_name: str, api_key: Optional[str] = None,
                 account_json_path: Optional[str] = None, path_prefix: Optional[str] = None, **_):
        self.bucket_name = bucket_name
        self.path_prefix = path_prefix
        self.api_key = api_key
        if os.getenv("GCP_CREDENTIALS"):
            ENV_GCP_CREDENTIALS = os.getenv("GCP_CREDENTIALS")
            parsed_crendentials = json.loads(ENV_GCP_CREDENTIALS)  # type: ignore
            self.credentials = service_account.Credentials.from_service_account_info(parsed_crendentials)
            self.storage_client = storage.Client(project=project_name, credentials=self.credentials)
        else:
            self.credentials = service_account.Credentials.from_service_account_file(account_json_path)
            self.storage_client = storage.Client.from_service_account_json(account_json_path)
        # self._init_container()

    def get(self, prefix: str, oid: str) -> BinaryIO:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.get_blob(self._get_blob_path(prefix, oid))
        return blob.download_as_string()  # type: ignore

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
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        if blob.exists():
            return bucket.get_blob(self._get_blob_path(prefix, oid)).size  # type: ignore
        else:
            raise ObjectNotFound("Object does not exist")

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
                    "expires_in": 900
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
        expires_in = timedelta(seconds=expires_in)
        disposition = f'attachment; filename={filename}' if filename else None
        url = blob.generate_signed_url(expiration=expires_in, method=http_method, credentials=self.credentials,
                                       response_disposition=disposition, version='v4')
        return url

    def _init_container(self):
        """Create the storage container
        """
        self.storage_client.get_bucket(self.bucket_name)
