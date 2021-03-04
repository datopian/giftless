import base64
import logging
import os
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from typing import Any, BinaryIO, Dict, Iterable, List, Optional
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobClient, BlobSasPermissions, BlobServiceClient, generate_blob_sas  # type: ignore

from giftless.storage import ExternalStorage, MultipartStorage, StreamingStorage

from .exc import ObjectNotFound

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


    def get(self, prefix: str, oid: str) -> Iterable[bytes]:
        return
    
    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        return

    def exists(self, prefix: str, oid: str) -> bool:
        return False

    def get_size(self, prefix: str, oid: str) -> int:
        return 100

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return

    def get_multipart_actions(self, prefix: str, oid: str, size: int, part_size: int, expires_in: int,
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return

