import logging
import os
from collections import namedtuple
from typing import Any, BinaryIO, Dict, Iterable, List, Optional

import boto3
import botocore

from giftless.storage import ExternalStorage, MultipartStorage, StreamingStorage

from giftless.storage.exc import ObjectNotFound

Block = namedtuple('Block', ['id', 'start', 'size'])

_log = logging.getLogger(__name__)


class AwsS3Storage(StreamingStorage, ExternalStorage, MultipartStorage):
    """Azure Blob Storage backend supporting streaming and direct-to-cloud
    transfers.
    """
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str,
                 aws_s3_bucket_name: str, path_prefix: str):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_s3_bucket_name = aws_s3_bucket_name
        self.path_prefix = path_prefix
        self.s3: boto3.session.Session.resource = boto3.resource('s3')

    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        return
    
    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        bucket = self.s3.Bucket(self.aws_s3_bucket_name)
        bucket.put_object(Key=self._get_blob_path(prefix, oid), Body=data_stream)
        return data_stream.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        s3_object = self._s3_object(prefix, oid)
        try:
            s3_object.load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                raise RuntimeError(e)
        return True

    def get_size(self, prefix: str, oid: str) -> int:
        if self.exists(prefix, oid):
            return self._s3_object(prefix, oid).content_length
        else:
            raise ObjectNotFound()

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return

    def get_multipart_actions(self, prefix: str, oid: str, size: int, part_size: int, expires_in: int,
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return

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
        return self.s3.Object(self.aws_s3_bucket_name, self._get_blob_path(prefix, oid))
