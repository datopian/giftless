"""External Backend Transfer Adapter

This transfer adapter offers 'basic' transfers by directing clients to upload
and download objects from an external storage service, such as AWS S3 or Azure
Blobs.

As long as external services support HTTP PUT / GET to do direct uploads /
downloads, this transfer adapter can work with them.

Different storage backends can be used with this adapter, as long as they
implement the `ExternalStorage` interface defined here.
"""

import os
from abc import ABC
from typing import Any, Dict

from giftless.transfer import TransferAdapter, ViewProvider
from giftless.transfer.basic_streaming import VerifiableStorage, VerifyView
from giftless.util import get_callable


class ExternalStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters
    """
    def get_upload_action(self, prefix: str, oid: str, size: int) -> Dict[str, Any]:
        pass

    def get_download_action(self, prefix: str, oid: str, size: int) -> Dict[str, Any]:
        pass


class BasicExternalBackendTransferAdapter(TransferAdapter, ViewProvider):

    def __init__(self, storage: ExternalStorage, default_action_lifetime: int):
        self.storage = storage
        self.action_lifetime = default_action_lifetime

    def upload(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        response = {"oid": oid,
                    "size": size,
                    "authenticated": True}

        prefix = os.path.join(organization, repo)
        response.update(self.storage.get_upload_action(prefix, oid, size))
        if response.get('actions', {}).get('upload'):
            response['actions']['verify'] = {
                "href": VerifyView.get_verify_url(organization, repo),
                "header": {},
                "expires_in": self.action_lifetime
            }

        return response

    def download(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        response = {"oid": oid,
                    "size": size}

        prefix = os.path.join(organization, repo)
        response.update(self.storage.get_download_action(prefix, oid, size))
        return response

    def register_views(self, app):
        VerifyView.register(app, init_argument=self.storage)


def factory(storage_class, storage_options, action_lifetime):
    """Factory for basic transfer adapter with external storage
    """
    storage = get_callable(storage_class, __name__)
    return BasicExternalBackendTransferAdapter(storage(**storage_options), action_lifetime)
