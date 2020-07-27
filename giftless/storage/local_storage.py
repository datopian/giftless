import os
import shutil
from typing import BinaryIO

from giftless.exc import NotFound
from giftless.storage import StreamingStorage


class LocalStorage(StreamingStorage):
    """Local storage implementation

    # TODO: do we need directory hashing?
    #       seems to me that in a single org/repo prefix this is not needed as we do not expect
    #       thousands of files per repo or thousands or repos per org
    """
    def __init__(self, path: str = None, **_):
        if path is None:
            path = 'lfs-storage'
        self.path = path
        self._create_path(self.path)

    def get(self, prefix: str, oid: str) -> BinaryIO:
        path = self._get_path(prefix, oid)
        if os.path.isfile(path):
            return open(path, 'br')
        else:
            raise NotFound("Requested object was not found")

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        path = self._get_path(prefix, oid)
        directory = os.path.dirname(path)
        self._create_path(directory)
        with open(path, 'bw') as dest:
            shutil.copyfileobj(data_stream, dest)
            return dest.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        return os.path.isfile(self._get_path(prefix, oid))

    def get_size(self, prefix: str, oid: str) -> int:
        if self.exists(prefix, oid):
            return os.path.getsize(self._get_path(prefix, oid))
        return 0

    def _get_path(self, prefix: str, oid: str) -> str:
        return os.path.join(self.path, prefix, oid)

    @staticmethod
    def _create_path(path):
        if not os.path.isdir(path):
            os.makedirs(path)
