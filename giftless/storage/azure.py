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


class AzureBlobsStorage(StreamingStorage, ExternalStorage, MultipartStorage):
    """Azure Blob Storage backend supporting streaming and direct-to-cloud
    transfers.
    """

    _PART_ID_BYTE_SIZE = 16

    def __init__(self, connection_string: str, container_name: str, path_prefix: Optional[str] = None,
                 enable_content_digest: bool = True, **_):
        self.container_name = container_name
        self.path_prefix = path_prefix
        self.blob_svc_client = BlobServiceClient.from_connection_string(connection_string)
        self.enable_content_digest = enable_content_digest

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
                    "href": self._get_signed_url(prefix, oid, expires_in, filename, create=True),
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
                    "href": self._get_signed_url(prefix, oid, expires_in, filename, read=True),
                    "header": {},
                    "expires_in": expires_in
                }
            }
        }

    def get_multipart_actions(self, prefix: str, oid: str, size: int, part_size: int, expires_in: int,
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get actions for a multipart upload
        """
        blocks = _calculate_blocks(size, part_size)
        uncommitted = self._get_uncommitted_blocks(prefix, oid, blocks)

        filename = extra.get('filename') if extra else None
        base_url = self._get_signed_url(prefix, oid, expires_in, filename, create=True, write=True, delete=True)
        parts = [self._create_part_request(base_url, b, expires_in) for b in blocks if b.id not in uncommitted]
        _log.info("There are %d uncommitted blocks pre-uploaded; %d parts still need to be uploaded",
                  len(uncommitted), len(parts))
        commit_body = self._create_commit_body(blocks)

        reply: Dict[str, Any] = {
            "actions": {
                "commit": {
                    "method": "PUT",
                    "href": f"{base_url}&{urlencode({'comp': 'blocklist'})}",
                    "body": commit_body,
                    "header": {
                        "Content-type": "text/xml; charset=utf8"
                    },
                    "expires_in": expires_in
                },
                "abort": {
                    "method": "DELETE",
                    "href": base_url,
                    "expires_in": expires_in
                }
            }
        }

        if parts:
            reply['actions']['parts'] = parts

        return reply

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

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int, filename: Optional[str] = None,
                        **permissions: bool) -> str:
        blob_name = self._get_blob_path(prefix, oid)
        permissions = BlobSasPermissions(**permissions)
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

    def _get_uncommitted_blocks(self, prefix: str, oid: str, blocks: List[Block]) -> Dict[int, int]:
        """Get list of uncommitted blocks from the server
        """
        blob_client = self.blob_svc_client.get_blob_client(container=self.container_name,
                                                           blob=self._get_blob_path(prefix, oid))
        try:
            committed_blocks, uncommitted_blocks = blob_client.get_block_list(block_list_type='all')
        except ResourceNotFoundError:
            return {}

        if committed_blocks:
            _log.warning(f"Committed blocks found for {oid}, this is unexpected state; restarting upload")
            blob_client.delete_blob()
            return {}

        try:
            # NOTE: The Azure python library already does ID base64 decoding for us, so we only case to int here
            existing_blocks = {int(b['id']): b['size'] for b in uncommitted_blocks}
        except ValueError:
            _log.warning("Some uncommitted blocks have unexpected ID format; restarting upload")
            return {}

        _log.debug("Found %d existing uncommitted blocks on server", len(existing_blocks))

        # Verify that existing blocks are the same as what we plan to upload
        for block in blocks:
            if block.id in existing_blocks and existing_blocks[block.id] != block.size:
                _log.warning("Uncommitted block size does not match our plan, restating upload")
                blob_client.delete_blob()
                return {}

        return existing_blocks

    def _create_part_request(self, base_url: str, block: Block, expires_in: int) -> Dict[str, Any]:
        """Create the part request object for a block
        """
        block_id = self._encode_block_id(block.id)
        part = {
            "href": f'{base_url}&comp=block&blockid={block_id}',
            "pos": block.start,
            "size": block.size,
            "expires_in": expires_in,
        }

        if self.enable_content_digest:
            part['want_digest'] = 'contentMD5'

        return part

    def _create_commit_body(self, blocks: List[Block]) -> str:
        """Create the body for a 'Put Blocks' request we use in commit

        NOTE: This is a simple XML construct, so we don't import / depend on XML construction API
        here. If this ever gets complex, it may be a good idea to rely on lxml or similar.
        """
        return '<?xml version="1.0" encoding="utf-8"?><BlockList>{}</BlockList>'.format(
            ''.join(['<Uncommitted>{}</Uncommitted>'.format(xml_escape(self._encode_block_id(b.id))) for b in blocks])
        )

    @classmethod
    def _encode_block_id(cls, b_id: int) -> str:
        """Encode a block ID in the manner expected by the Azure API
        """
        return base64.b64encode(str(b_id).zfill(cls._PART_ID_BYTE_SIZE).encode('ascii')).decode('ascii')


def _calculate_blocks(file_size: int, part_size: int) -> List[Block]:
    """Calculate the list of blocks in a blob

    >>> _calculate_blocks(30, 10)
    [Block(id=0, start=0, size=10), Block(id=1, start=10, size=10), Block(id=2, start=20, size=10)]

    >>> _calculate_blocks(28, 10)
    [Block(id=0, start=0, size=10), Block(id=1, start=10, size=10), Block(id=2, start=20, size=8)]

    >>> _calculate_blocks(7, 10)
    [Block(id=0, start=0, size=7)]

    >>> _calculate_blocks(0, 10)
    []
    """
    full_blocks = file_size // part_size
    last_block_size = file_size % part_size
    blocks = [Block(id=i, start=i * part_size, size=part_size) for i in range(full_blocks)]

    if last_block_size:
        blocks.append(Block(id=full_blocks, start=full_blocks * part_size, size=last_block_size))

    return blocks
