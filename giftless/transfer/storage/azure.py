import os
from datetime import datetime, timedelta, timezone
from typing import Any, BinaryIO, Dict, Optional

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobClient, BlobSasPermissions, BlobServiceClient, generate_blob_sas  # type: ignore

from giftless.transfer.basic_external import ExternalStorage
from giftless.transfer.basic_streaming import StreamingStorage


class AzureBlobsStorage(StreamingStorage, ExternalStorage):
    """Azure Blob Storage backend supporting streaming and direct-to-cloud
    transfers.

    """
    def __init__(self, connection_string: str, container_name: str, path_prefix: Optional[str] = None, **_):
        self.container_name = container_name
        self.path_prefix = path_prefix
        self.blob_svc_client = BlobServiceClient.from_connection_string(connection_string)
        self._init_container()

    def get(self, prefix: str, oid: str) -> BinaryIO:
        blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                           blob=self._get_blob_path(prefix, oid))
        return blob_client.download_blob().chunks()  # type: ignore

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                           blob=self._get_blob_path(prefix, oid))
        blob_client.upload_blob(data_stream)
        return data_stream.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        try:
            self.get_size(prefix, oid)
            return True
        except ResourceNotFoundError:
            return False

    def get_size(self, prefix: str, oid: str) -> int:
        blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                           blob=self._get_blob_path(prefix, oid))
        props = blob_client.get_blob_properties()
        return props.size  # type: ignore

    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        try:
            return self.get_size(prefix, oid) == size
        except ResourceNotFoundError:
            return False

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int) -> Dict[str, Any]:
        if self.verify_object(prefix, oid, size):
            # No upload required, we already have this object
            return {}

        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(prefix, oid, expires_in),
                    "header": {
                        "x-ms-blob-type": "BlockBlob",
                    },
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int) -> Dict[str, Any]:
        try:
            if self.get_size(prefix, oid) != size:
                return {"error": {
                    "code": 422,
                    "message": "Object size does not match"
                }}
        except ResourceNotFoundError:
            # Object does not exist, return 404
            return {"error": {
                "code": 404,
                "message": "Object does not exist"
            }}

        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(prefix, oid, expires_in),
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

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int) -> str:
        blob_name = self._get_blob_path(prefix, oid)
        permissions = BlobSasPermissions(read=True, create=True)
        token_expires = (datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in))
        sas_token = generate_blob_sas(account_name=self.blob_svc_client.account_name,
                                      account_key=self.blob_svc_client.credential.account_key,
                                      container_name=self.container_name,
                                      blob_name=blob_name,
                                      permission=permissions,
                                      expiry=token_expires)

        blob_client = BlobClient(self.blob_svc_client.url, container_name=self.container_name, blob_name=blob_name,
                                 credential=sas_token)
        return blob_client.url  # type: ignore

    def _init_container(self):
        """Create the storage container
        """
        try:
            self.blob_svc_client.create_container(self.container_name)
        except ResourceExistsError:
            pass
