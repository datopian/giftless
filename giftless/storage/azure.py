import os
from datetime import datetime, timedelta, timezone
from typing import Any, BinaryIO, Dict, Iterable, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobClient, BlobSasPermissions, BlobServiceClient, generate_blob_sas  # type: ignore

from giftless.storage import ExternalStorage, StreamingStorage

from .exc import ObjectNotFound


class AzureBlobsStorage(StreamingStorage, ExternalStorage):
    """Azure Blob Storage backend supporting streaming and direct-to-cloud
    transfers.

    """
    def __init__(self, connection_string: str, container_name: str, path_prefix: Optional[str] = None, **_):
        self.container_name = container_name
        self.path_prefix = path_prefix
        self.blob_svc_client = BlobServiceClient.from_connection_string(connection_string)

    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                           blob=self._get_blob_path(prefix, oid))
        try:
            return blob_client.download_blob().chunks()  # type: ignore
        except ResourceNotFoundError:
            raise ObjectNotFound("Object does not exist")

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                           blob=self._get_blob_path(prefix, oid))
        blob_client.upload_blob(data_stream)
        return data_stream.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        try:
            self.get_size(prefix, oid)
            return True
        except ObjectNotFound:
            return False

    def get_size(self, prefix: str, oid: str) -> int:
        try:
            blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                               blob=self._get_blob_path(prefix, oid))
            props = blob_client.get_blob_properties()
            return props.size  # type: ignore
        except ResourceNotFoundError:
            raise ObjectNotFound("Object does not exist")

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filename = extra.get('filename') if extra else None
        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(prefix, oid, expires_in, filename),
                    "header": {
                        "x-ms-blob-type": "BlockBlob",
                    },
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
                    "href": self._get_signed_url(prefix, oid, expires_in, filename),
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

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int, filename: Optional[str] = None) -> str:
        blob_name = self._get_blob_path(prefix, oid)
        permissions = BlobSasPermissions(read=True, create=True)
        token_expires = (datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in))

        extra_args = {}
        if filename:
            extra_args['content_disposition'] = f'attachment; filename="{filename}"'

        sas_token = generate_blob_sas(account_name=self.blob_svc_client.account_name,
                                      account_key=self.blob_svc_client.credential.account_key,
                                      container_name=self.container_name,
                                      blob_name=blob_name,
                                      permission=permissions,
                                      expiry=token_expires,
                                      **extra_args)

        blob_client = BlobClient(self.blob_svc_client.url, container_name=self.container_name, blob_name=blob_name,
                                 credential=sas_token)
        return blob_client.url  # type: ignore
