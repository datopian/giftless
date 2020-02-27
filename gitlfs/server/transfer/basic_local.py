"""Local Transfer Adapter, most likely to be used with 'basic' transfers

Stores files on the local disk.
"""
import os
from typing import Dict, Optional

from gitlfs.server.transfer import TransferAdapter, ViewProvider
from gitlfs.server.util import get_callable
from gitlfs.server.view import BaseView


class LocalStorage:
    """Local storage implementation
    """
    def __init__(self, path: str = None):
        if path is None:
            path = 'lfs-storage'
        self.path = path
        self._init_storage_path()

    def get(self, path: str):
        pass

    def put(self, path: str, data_stream):
        pass

    def exists(self, path: str) -> bool:
        pass

    def get_size(self, path: str) -> int:
        pass

    def _init_storage_path(self):
        if not os.path.isdir(self.path):
            os.makedirs(self.path)


class LocalTransferAdapter(TransferAdapter, ViewProvider):

    def __init__(self, storage: Optional[LocalStorage]):
        self.storage = storage

    def upload(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        return {"data": ['upload', organization, repo, oid, size]}

    def download(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        return {"data": ['upload', organization, repo, oid, size]}

    def get_views(self):
        return [ObjectsView]


class ObjectsView(BaseView):

    route_base = '<organization>/<repo>/objects/storage'

    def put(self, organization, repo, oid):
        """Upload a file to local storage
        """
        return ["local-base-put", organization, repo, oid]

    def get(self, organization, repo, oid):
        """Upload a file to local storage
        """
        return ["local-base-get", organization, repo, oid]

    def verify(self, organization, repo, oid):
        return ["local-base-verify", organization, repo, oid]


def factory(storage_class, storage_options):
    """Factory for basic transfer adapter with local storage
    """
    storage = get_callable(storage_class, __name__)
    return LocalTransferAdapter(storage(**storage_options))
