import logging
import os
import urllib
from collections import namedtuple
from typing import Any, BinaryIO, Dict, Iterable, List, Optional

import boto3
import botocore

from giftless.storage import ExternalStorage, MultipartStorage, StreamingStorage

from giftless.storage.exc import ObjectNotFound

Block = namedtuple('Block', ['id', 'start', 'size'])

_log = logging.getLogger(__name__)


class AwsS3Storage(StreamingStorage, ExternalStorage, MultipartStorage):
    """AWS S3 Blob Storage backend.
    """

    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str,
                 aws_s3_bucket_name: str, path_prefix: str):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_s3_bucket_name = aws_s3_bucket_name
        self.path_prefix = path_prefix
        self.s3: boto3.session.Session.resource = boto3.resource('s3')
        self.s3_client = boto3.client('s3')

    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        if not self.exists(prefix, oid):
            raise ObjectNotFound()
        return self._s3_object(prefix, oid).get()['Body']

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        bucket = self.s3.Bucket(self.aws_s3_bucket_name)
        res = bucket.put_object(Key=self._get_blob_path(prefix, oid), Body=data_stream)
        return res.content_length

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
        # TODO: The current approach with urlencoding fields doesn't work
        # AWS returns "The specified method is not allowed against this resource." error
        response = self.s3_client.generate_presigned_post(self.aws_s3_bucket_name,
                                                          self._get_blob_path(prefix, oid),
                                                          ExpiresIn=expires_in,
                                                          **extra
                                                          )
        params = urllib.parse.urlencode(response['fields'])
        href = f"{response['url']}?{params}"
        return {
            "actions": {
                "upload": {
                    "href": href,
                    "header": {},
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        filename = extra.get('filename') if extra else oid
        params_ = {
            'Bucket': self.aws_s3_bucket_name,
            'Key': self._get_blob_path(prefix, oid),
            'ResponseContentDisposition': f"attachment; filename = {filename}"
        }
        response = self.s3_client.generate_presigned_url('get_object',
                                                         Params=params_,
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
