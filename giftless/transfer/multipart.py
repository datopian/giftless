"""Multipart Transfer Adapter."""

import posixpath
from typing import Any

from flask import Flask

from giftless.storage import MultipartStorage, exc
from giftless.transfer import PreAuthorizingTransferAdapter
from giftless.transfer.basic_streaming import VerifyView
from giftless.util import get_callable
from giftless.view import ViewProvider

DEFAULT_PART_SIZE = 10240000  # 10MB (-ish)
DEFAULT_ACTION_LIFETIME = 6 * 60 * 60  # 6 hours


class MultipartTransferAdapter(PreAuthorizingTransferAdapter, ViewProvider):
    """Transfer Adapter supporting multipart methods."""

    def __init__(
        self,
        storage: MultipartStorage,
        default_action_lifetime: int,
        max_part_size: int = DEFAULT_PART_SIZE,
    ) -> None:
        super().__init__()
        self.storage = storage
        self.max_part_size = max_part_size
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

        actions = self.storage.get_multipart_actions(
            prefix, oid, size, self.max_part_size, self.action_lifetime, extra
        )
        response.update(actions)
        if response.get("actions"):
            response["authenticated"] = True
            headers = self._preauth_headers(
                organization,
                repo,
                actions={"verify"},
                oid=oid,
                lifetime=self.VERIFY_LIFETIME,
            )
            response["actions"]["verify"] = {  # type: ignore[index]
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
            response["authenticated"] = True

        return response

    def register_views(self, app: Flask) -> None:
        # TODO @rufuspollock: this is broken. Need to find a smarter
        # way for multiple transfer adapters to provide the same view
        #  -- broken: VerifyView.register(app, init_argument=self.storage)
        # TODO @athornton: does this maybe indicate a classvar shadowing or
        # updating issue? Investigate that.
        if isinstance(self.storage, ViewProvider):
            self.storage.register_views(app)

    def _check_object(self, prefix: str, oid: str, size: int) -> None:
        """Raise specific domain error if object is not valid.

        NOTE: this does not use storage.verify_object directly because
        we want ObjectNotFoundError errors to be propagated if raised.
        """
        if self.storage.get_size(prefix, oid) != size:
            raise exc.InvalidObjectError("Object size does not match")


def factory(
    storage_class: Any,
    storage_options: Any,
    action_lifetime: int = DEFAULT_ACTION_LIFETIME,
    max_part_size: int = DEFAULT_PART_SIZE,
) -> MultipartTransferAdapter:
    """Build a multipart transfer adapter with storage."""
    try:
        storage = get_callable(storage_class, __name__)
    except (AttributeError, ImportError):
        raise ValueError(
            f"Unable to load storage module: {storage_class}"
        ) from None
    return MultipartTransferAdapter(
        storage(**storage_options),
        action_lifetime,
        max_part_size=max_part_size,
    )
