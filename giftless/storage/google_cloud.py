import base64
import io
import json
import posixpath
from datetime import timedelta
from typing import Any, BinaryIO, Dict, Optional, Union

import google.auth  # type: ignore
from google.auth import impersonated_credentials
from google.cloud import storage  # type: ignore
from google.oauth2 import service_account  # type: ignore

from giftless.storage import ExternalStorage, StreamingStorage

from .exc import ObjectNotFound


class GoogleCloudStorage(StreamingStorage, ExternalStorage):
    """Google Cloud Storage backend supporting direct-to-cloud
    transfers.
    """

    def __init__(self,
                 project_name: str,
                 bucket_name: str,
                 account_key_file: Optional[str] = None,
                 account_key_base64: Optional[str] = None,
                 path_prefix: Optional[str] = None,
                 serviceaccount_email: Optional[str] = None,
                 **_):
        self.bucket_name = bucket_name
        self.path_prefix = path_prefix
        self.credentials: Optional[service_account.Credentials] = self._load_credentials(account_key_file, account_key_base64)
        self.storage_client = storage.Client(project=project_name, credentials=self.credentials)
        if not self.credentials:
            if not serviceaccount_email:
                raise ValueError(
                    "If no account key is given, serviceaccount_email must "
                    "be set in order to use workload identity."
                )
            self._serviceaccount_email=serviceaccount_email

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
        disposition = extra.get('disposition', 'attachment') if extra else 'attachment'

        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(
                        prefix, oid, expires_in=expires_in, filename=filename, disposition=disposition),
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
        return posixpath.join(storage_prefix, prefix, oid)

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int, http_method: str = 'GET',
                        filename: Optional[str] = None, disposition: Optional[str] = None) -> str:
        creds: Optional[Union[service_account.Credentials, impersonated_credentials.Credentials]] = self.credentials
        if creds is None:
            # Try Workload Identity
            creds = self._get_workload_identity_credentials(expires_in)
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        disposition = f'attachment; filename={filename}' if filename else None
        if filename and disposition:
            disposition = f'{disposition}; filename="{filename}"'

        url: str = blob.generate_signed_url(expiration=timedelta(seconds=expires_in), method=http_method, version='v4',
                                            response_disposition=disposition, credentials=creds)
        return url

    @staticmethod
    def _load_credentials(account_key_file: Optional[str], account_key_base64: Optional[str]) \
            -> Optional[service_account.Credentials]:
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
            return None  # Will use Workload Identity if available

    def _get_workload_identity_credentials(self, expires_in: int) -> impersonated_credentials.Credentials:
        lifetime = expires_in
        if lifetime > 3600:
            lifetime = 3600  # Signing credentials are good for one hour max
        email = self._serviceaccount_email
        def_creds, _ = google.auth.default()
        # Do the switcheroo: impersonate ourselves with an account that can
        # grant a temporary signing token
        return impersonated_credentials.Credentials(
            source_credentials=def_creds,
            target_principal=email,
            target_scopes=(
                "https://www.googleapis.com/auth/devstorage.read_only",
                "https://www.googleapis.com/auth/devstorage.read_write"
            ),
            lifetime=lifetime
        )
