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
from typing import Any, Dict, Optional

from giftless.storage import ExternalStorage, exc
from giftless.transfer import PreAuthorizingTransferAdapter, ViewProvider
from giftless.transfer.basic_streaming import VerifyView
from giftless.util import get_callable


class BasicExternalBackendTransferAdapter(PreAuthorizingTransferAdapter, ViewProvider):

    def __init__(self, storage: ExternalStorage, default_action_lifetime: int):
        self.storage = storage
        self.action_lifetime = default_action_lifetime

    def upload(self, organization: str, repo: str, oid: str, size: int, extra: Optional[Dict[str, Any]] = None) -> Dict:
        prefix = os.path.join(organization, repo)
        response = {"oid": oid,
                    "size": size}

        if self.storage.verify_object(prefix, oid, size):
            # No upload required, we already have this object
            return response

        response.update(self.storage.get_upload_action(prefix, oid, size, self.action_lifetime, extra))
        if response.get('actions', {}).get('upload'):  # type: ignore
            response['authenticated'] = True
            headers = self._preauth_headers(organization, repo, actions={'verify'}, oid=oid,
                                            lifetime=self.VERIFY_LIFETIME)
            response['actions']['verify'] = {  # type: ignore
                "href": VerifyView.get_verify_url(organization, repo),
                "header": headers,
                "expires_in": self.VERIFY_LIFETIME
            }

        return response

    def download(self, organization: str, repo: str, oid: str, size: int,
                 extra: Optional[Dict[str, Any]] = None) -> Dict:
        prefix = os.path.join(organization, repo)
        response = {"oid": oid,
                    "size": size}

        try:
            self._check_object(prefix, oid, size)
            response.update(self.storage.get_download_action(prefix, oid, size, self.action_lifetime, extra))
        except exc.StorageError as e:
            response['error'] = e.as_dict()

        if response.get('actions', {}).get('download'):  # type: ignore
            response['authenticated'] = True

        return response

    def register_views(self, app):
        VerifyView.register(app, init_argument=self.storage)

    def _check_object(self, prefix: str, oid: str, size: int):
        """Raise specific domain error if object is not valid

        NOTE: this does not use storage.verify_object directly because
        we want ObjectNotFound errors to be propagated if raised
        """
        if self.storage.get_size(prefix, oid) != size:
            raise exc.InvalidObject('Object size does not match')


def factory(storage_class, storage_options, action_lifetime):
    """Factory for basic transfer adapter with external storage
    """
    storage = get_callable(storage_class, __name__)
    return BasicExternalBackendTransferAdapter(storage(**storage_options), action_lifetime)
