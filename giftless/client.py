"""A simple Git LFS client

This is here mainly for testing and experimentation purposes; It is not intended for production
use, but for the purpose of testing some of the functionality provided by the Giftless server.
"""
import base64
import hashlib
import logging
import os
import sys
from typing import Any, BinaryIO, Dict, Optional, Tuple, Union
from urllib.parse import urlencode

import requests

from .transfer.types import MultipartUploadObjectAttributes, ObjectAttributes

FILE_READ_BUFFER_SIZE = 4 * 1024 * 1000  # 4mb, why not

_log = logging.getLogger(__name__)


class LfsClient:

    def __init__(self, lfs_server_url: str):
        self._url = lfs_server_url.rstrip('/')

    def upload(self, file: BinaryIO, organization: str, repo: str):
        """Upload a file to LFS storage
        """
        object_attrs = self._get_object_attrs(file)
        payload = {"transfers": ["multipart-basic", "basic"],
                   "operation": "upload",
                   "objects": [object_attrs]}
        batch_reply = requests.post(self._url_for(organization, repo, 'objects', 'batch'), json=payload)
        if batch_reply.status_code != 200:
            raise RuntimeError("Unexpected reply from LFS server: {}".format(batch_reply))

        response = batch_reply.json()
        _log.debug("Got reply for batch request: %s", response)

        if response['transfer'] == 'basic':
            return self._upload_basic(file, response['objects'][0])
        elif response['transfer'] == 'multipart-basic':
            return self._upload_multipart(file, response['objects'][0])

    def _url_for(self, *segments: str, **params: str) -> str:
        path = os.path.join(*segments)
        url = f'{self._url}/{path}'
        if params:
            url = f'{url}?{urlencode(params)}'
        return url

    def _upload_basic(self, file: BinaryIO, upload_object: 'MultipartUploadObjectAttributes'):
        """Do a basic upload
        TODO: refactor this into a separate class
        """
        raise NotImplementedError("Basic uploads are not implemented yet")

    def _upload_multipart(self, file: BinaryIO, upload_object: 'MultipartUploadObjectAttributes'):
        """Do a multipart upload
        TODO: refactor this into a separate class
        """
        actions = upload_object.get('actions')
        if not actions:
            _log.info("No actions, file already exists")
            return

        init_action = actions.get('init')
        if init_action:
            _log.info(f"Sending multipart init action to {init_action['href']}")
            response = self._send_request(init_action['href'],
                                          method=init_action.get('method', 'POST'),
                                          headers=init_action.get('header', {}),
                                          body=init_action.get('body'))
            if response.status_code // 100 != 2:
                raise RuntimeError(f"init failed with error status code: {response.status_code}")

        for p, part in enumerate(actions.get('parts', [])):
            _log.info("Uploading part %d/%d", p + 1, len(actions['parts']))
            self._send_part_request(file, **part)

        commit_action = actions.get('commit')
        if commit_action:
            _log.info(f"Sending multipart commit action to {commit_action['href']}")
            response = self._send_request(commit_action['href'],
                                          method=commit_action.get('method', 'POST'),
                                          headers=commit_action.get('header', {}),
                                          body=commit_action.get('body'))
            if response.status_code // 100 != 2:
                raise RuntimeError(f"commit failed with error status code: {response.status_code}: {response.text}")

        verify_action = actions.get('verify')
        if verify_action:
            _log.info(f"Sending verify action to {verify_action['href']}")
            response = requests.post(verify_action['href'], headers=verify_action.get('header', {}),
                                     json={"oid": upload_object['oid'], "size": upload_object['size']})
            if response.status_code // 100 != 2:
                raise RuntimeError(f"verify failed with error status code: {response.status_code}: {response.text}")

    @staticmethod
    def _get_object_attrs(file: BinaryIO) -> 'ObjectAttributes':
        digest = hashlib.sha256()
        try:
            while True:
                data = file.read(FILE_READ_BUFFER_SIZE)
                if data:
                    digest.update(data)
                else:
                    break

            size = file.tell()
            oid = digest.hexdigest()
        finally:
            file.seek(0)

        return ObjectAttributes(oid=oid, size=size)

    def _send_part_request(self, file: BinaryIO, href: str, method: str = 'PUT', pos: int = 0,
                           size: Optional[int] = None, want_digest: Optional[str] = None,
                           header: Optional[Dict[str, Any]] = None, **_):
        """Upload a part
        """
        file.seek(pos)
        if size:
            data = file.read(size)
        else:
            data = file.read()

        if header is None:
            header = {}

        if want_digest:
            digest_type, digest_value = self._calculate_digest(data, want_digest)
            header.update({digest_type: digest_value})

        reply = self._send_request(href, method=method, headers=header, body=data)
        if reply.status_code // 100 != 2:
            raise RuntimeError(f"Unexpected reply from server for part: {reply.status_code} {reply.text}")

    @staticmethod
    def _send_request(href: str, method: str, headers: Dict[str, str], body: Union[bytes, str, None] = None) \
            -> requests.Response:
        """Send an arbitrary HTTP request
        """
        reply = requests.session().request(method=method, url=href, headers=headers, data=body)
        return reply

    @staticmethod
    def _calculate_digest(data: bytes, want_digest: str) -> Tuple[str, str]:
        """TODO: Properly implement this
        """
        if want_digest == 'contentMD5':
            digest = base64.b64encode(hashlib.md5(data).digest()).decode('ascii')
            return 'Content-MD5', digest
        else:
            raise RuntimeError(f"Don't know how to handle want_digest value: {want_digest}")


def _main():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)-15s %(name)-24s %(levelname)-8s %(message)s')

    try:
        source = sys.argv[1]
        server_url = sys.argv[2]
    except IndexError:
        sys.stderr.write(f'Usage: {sys.argv[0]} <file> <LFS server URL>\n')
        sys.exit(1)

    client = LfsClient(server_url)
    with open(source, 'rb') as f:
        client.upload(f, 'myorg', 'myrepo')


if __name__ == '__main__':
    _main()
