import os
from typing import Any, BinaryIO, Dict, Iterable, Optional

import boto3  # type: ignore
import botocore  # type: ignore

from giftless.storage import ExternalStorage, StreamingStorage
from giftless.storage.exc import ObjectNotFound
from giftless.util import safe_filename


class AmazonS3Storage(StreamingStorage, ExternalStorage):
    """AWS S3 Blob Storage backend.
    """

    def __init__(self, bucket_name: str, path_prefix: Optional[str] = None, **_):
        self.bucket_name = bucket_name
        self.path_prefix = path_prefix
        self.s3 = boto3.resource('s3')
        self.s3_client = boto3.client('s3')

    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        if not self.exists(prefix, oid):
            raise ObjectNotFound()
        result: Iterable[bytes] = self._s3_object(prefix, oid).get()['Body']
        return result

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        completed = []

        def upload_callback(size):
            completed.append(size)

        bucket = self.s3.Bucket(self.bucket_name)
        bucket.upload_fileobj(data_stream, self._get_blob_path(prefix, oid), Callback=upload_callback)
        return sum(completed)

    def exists(self, prefix: str, oid: str) -> bool:
        s3_object = self._s3_object(prefix, oid)
        try:
            s3_object.load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                raise e
        return True

    def get_size(self, prefix: str, oid: str) -> int:
        if self.exists(prefix, oid):
            result: int = self._s3_object(prefix, oid).content_length
            return result
        else:
            raise ObjectNotFound()

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {
            'Bucket': self.bucket_name,
            'Key': self._get_blob_path(prefix, oid)
        }
        response = self.s3_client.generate_presigned_url('put_object',
                                                         Params=params,
                                                         ExpiresIn=expires_in
                                                         )
        return {
            "actions": {
                "upload": {
                    "href": response,
                    "header": {},
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, str]] = None) -> Dict[str, Any]:

        raw_filename = extra.get('filename') if extra else oid
        assert raw_filename
        filename = safe_filename(raw_filename)
        params = {
            'Bucket': self.bucket_name,
            'Key': self._get_blob_path(prefix, oid),
            'ResponseContentDisposition': f"attachment;filename={filename}"
        }
        response = self.s3_client.generate_presigned_url('get_object',
                                                         Params=params,
                                                         ExpiresIn=expires_in
                                                         )
        return {
            "actions": {
                "download": {
                    "href": response,
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

    def _s3_object(self, prefix, oid):
        return self.s3.Object(self.bucket_name, self._get_blob_path(prefix, oid))
