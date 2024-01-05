"""Amazon S3 backend."""
import base64
import binascii
import posixpath
from collections.abc import Iterable
from typing import Any, BinaryIO

import boto3
import botocore

from giftless.storage import ExternalStorage, StreamingStorage
from giftless.storage.exc import ObjectNotFoundError
from giftless.util import safe_filename


class AmazonS3Storage(StreamingStorage, ExternalStorage):
    """AWS S3 Blob Storage backend."""

    def __init__(
        self,
        bucket_name: str,
        path_prefix: str | None = None,
        endpoint: str | None = None,
        **_: Any,
    ) -> None:
        self.bucket_name = bucket_name
        self.path_prefix = path_prefix
        self.s3 = boto3.resource("s3", endpoint_url=endpoint)
        self.s3_client = boto3.client("s3", endpoint_url=endpoint)

    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        if not self.exists(prefix, oid):
            raise ObjectNotFoundError
        result: Iterable[bytes] = self._s3_object(prefix, oid).get()["Body"]
        return result

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        completed: list[int] = []

        def upload_callback(size: int) -> None:
            completed.append(size)

        bucket = self.s3.Bucket(self.bucket_name)
        bucket.upload_fileobj(
            data_stream,
            self._get_blob_path(prefix, oid),
            Callback=upload_callback,
        )
        return sum(completed)

    def exists(self, prefix: str, oid: str) -> bool:
        try:
            self.get_size(prefix, oid)
        except ObjectNotFoundError:
            return False
        return True

    def get_size(self, prefix: str, oid: str) -> int:
        try:
            result: int = self._s3_object(prefix, oid).content_length
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise ObjectNotFoundError from None
            raise
        return result

    def get_upload_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base64_oid = base64.b64encode(binascii.a2b_hex(oid)).decode("ascii")
        params = {
            "Bucket": self.bucket_name,
            "Key": self._get_blob_path(prefix, oid),
            "ContentType": "application/octet-stream",
            "ChecksumSHA256": base64_oid,
        }
        response = self.s3_client.generate_presigned_url(
            "put_object", Params=params, ExpiresIn=expires_in
        )
        return {
            "actions": {
                "upload": {
                    "href": response,
                    "header": {
                        "Content-Type": "application/octet-stream",
                        "x-amz-checksum-sha256": base64_oid,
                    },
                    "expires_in": expires_in,
                }
            }
        }

    def get_download_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        params = {
            "Bucket": self.bucket_name,
            "Key": self._get_blob_path(prefix, oid),
        }

        filename = extra.get("filename") if extra else None
        disposition = (
            extra.get("disposition", "attachment") if extra else "attachment"
        )

        if filename and disposition:
            filename = safe_filename(filename)
            params[
                "ResponseContentDisposition"
            ] = f'attachment; filename="{filename}"'
        elif disposition:
            params["ResponseContentDisposition"] = disposition

        response = self.s3_client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )
        return {
            "actions": {
                "download": {
                    "href": response,
                    "header": {},
                    "expires_in": expires_in,
                }
            }
        }

    def _get_blob_path(self, prefix: str, oid: str) -> str:
        """Get the path to a blob in storage."""
        if not self.path_prefix:
            storage_prefix = ""
        elif self.path_prefix[0] == "/":
            storage_prefix = self.path_prefix[1:]
        else:
            storage_prefix = self.path_prefix
        return posixpath.join(storage_prefix, prefix, oid)

    def _s3_object(self, prefix: str, oid: str) -> Any:
        return self.s3.Object(
            self.bucket_name, self._get_blob_path(prefix, oid)
        )
