"""Local Transfer Adapter, most likely to be used with 'basic' transfers

Stores files on the local disk.
"""
import os
from typing import Dict, Optional

from flask import url_for

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


class BasicStreamedTransferAdapter(TransferAdapter, ViewProvider):

    def __init__(self, storage: Optional[LocalStorage], action_lifetime: int):
        self.storage = storage
        self.action_lifetime = action_lifetime

    def upload(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        # TODO: check if file exists, if so ommit the "actions" key
        return {"oid": oid,
                "size": size,
                "authenticated": True,
                "actions": {
                    "upload": {
                        "href": ObjectsView.get_storage_url('put', organization, repo, oid),
                        "header": {
                            "Authorization": "Basic yourmamaisauthorized"
                        },
                        "expires_in": self.action_lifetime
                    },
                    "verify": {
                        "href": ObjectsView.get_storage_url('verify', organization, repo, oid),
                        "header": {
                            "Authorization": "Basic yourmamaisauthorized"
                        },
                        "expires_in": self.action_lifetime
                    }
                }}

    def download(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        # TODO: check that the user can download the file (exists?)
        return {"oid": oid,
                "size": size,
                "authenticated": True,
                "actions": {
                    "download": {
                        "href": ObjectsView.get_storage_url('get', organization, repo, oid),
                        "header": {
                            "Authorization": "Basic yourmamaisauthorized"
                        },
                        "expires_in": self.action_lifetime
                    }
                }}

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

    @classmethod
    def get_storage_url(cls, operation: str, organization: str, repo: str, oid: str) -> str:
        """Get the URL for upload / download requests for this object
        """
        op_name = f'{cls.__name__}:{operation}'
        return url_for(op_name, organization=organization, repo=repo, oid=oid, _external=True)


def factory(storage_class, storage_options, action_lifetime):
    """Factory for basic transfer adapter with local storage
    """
    storage = get_callable(storage_class, __name__)
    return BasicStreamedTransferAdapter(storage(**storage_options), action_lifetime)
