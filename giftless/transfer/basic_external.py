"""External Backend Transfer Adapter.

This transfer adapter offers 'basic' transfers by directing clients to upload
and download objects from an external storage service, such as AWS S3 or Azure
Blobs.

As long as external services support HTTP PUT / GET to do direct uploads /
downloads, this transfer adapter can work with them.

Different storage backends can be used with this adapter, as long as they
implement the `ExternalStorage` interface defined in giftless.storage.
"""

import posixpath
from typing import Any

from flask import Flask

from giftless.storage import ExternalStorage, exc
from giftless.transfer import PreAuthorizingTransferAdapter
from giftless.transfer.basic_streaming import VerifyView
from giftless.util import get_callable
from giftless.view import ViewProvider


class BasicExternalBackendTransferAdapter(
    PreAuthorizingTransferAdapter, ViewProvider
):
    """Provides External Transfer Adapter.

    TODO @athornton: inherently PreAuthorizing feels weird.  Investigate
    whether there's refactoring/mixin work we can do here.
    """

    def __init__(
        self, storage: ExternalStorage, default_action_lifetime: int
    ) -> None:
        super().__init__()
        self.storage = storage
        self.action_lifetime = default_action_lifetime

    def upload(
        self,
        organization: str,
        repo: str,
        oid: str,
        size: int,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        prefix = posixpath.join(organization, repo)
        response = {"oid": oid, "size": size}

        if self.storage.verify_object(prefix, oid, size):
            # No upload required, we already have this object
            return response

        response.update(
            self.storage.get_upload_action(
                prefix, oid, size, self.action_lifetime, extra
            )
        )
        if response.get("actions", {}).get("upload"):  # type:ignore[attr-defined]
            response["authenticated"] = self._provides_preauth
            headers = self._preauth_headers(
                organization,
                repo,
                actions={"verify"},
                oid=oid,
                lifetime=self.VERIFY_LIFETIME,
            )
            response["actions"]["verify"] = {  # type:ignore[index]
                "href": VerifyView.get_verify_url(organization, repo),
                "header": headers,
                "expires_in": self.VERIFY_LIFETIME,
            }

        return response

    def download(
        self,
        organization: str,
        repo: str,
        oid: str,
        size: int,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        prefix = posixpath.join(organization, repo)
        response = {"oid": oid, "size": size}

        try:
            self._check_object(prefix, oid, size)
            response.update(
                self.storage.get_download_action(
                    prefix, oid, size, self.action_lifetime, extra
                )
            )
        except exc.StorageError as e:
            response["error"] = e.as_dict()

        if response.get("actions", {}).get("download"):  # type:ignore[attr-defined]
            response["authenticated"] = self._provides_preauth

        return response

    def register_views(self, app: Flask) -> None:
        VerifyView.register(app, init_argument=self.storage)

    def _check_object(self, prefix: str, oid: str, size: int) -> None:
        """Raise specific domain error if object is not valid.

        NOTE: this does not use storage.verify_object directly because
        we want ObjectNotFoundError errors to be propagated if raised
        """
        if self.storage.get_size(prefix, oid) != size:
            raise exc.InvalidObjectError("Object size does not match")


def factory(
    storage_class: Any, storage_options: Any, action_lifetime: int
) -> BasicExternalBackendTransferAdapter:
    """Build a basic transfer adapter with external storage."""
    storage = get_callable(storage_class, __name__)
    return BasicExternalBackendTransferAdapter(
        storage(**storage_options), action_lifetime
    )
