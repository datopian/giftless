"""Transfer adapters.

See
https://github.com/git-lfs/git-lfs/blob/master/docs/api/basic-transfers.md
for more information about what transfer APIs do in Git LFS.
"""
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any, cast

from flask import Flask

from giftless.auth import (
    Authentication,
    PreAuthorizedActionAuthenticator,
    authentication,
)
from giftless.auth.identity import Identity
from giftless.util import add_query_params, get_callable
from giftless.view import ViewProvider

_registered_adapters: dict[str, "TransferAdapter"] = {}


class TransferAdapter(ABC):  # noqa:B024
    """A transfer adapter tells Git LFS Server how to respond to batch
    API requests.
    """

    # We don't want these to be abstract methods because the test suite
    # actually instantiates a TransferAdapter, even though it's an ABC.
    def upload(
        self,
        organization: str,
        repo: str,
        oid: str,
        size: int,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        raise NotImplementedError(
            "This transfer adapter is not fully implemented"
        )

    def download(
        self,
        organization: str,
        repo: str,
        oid: str,
        size: int,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        raise NotImplementedError(
            "This transfer adapter is not fully implemented"
        )

    def get_action(
        self, name: str, organization: str, repo: str
    ) -> Callable[[str, int], dict]:
        """Shortcut for quickly getting an action callable for
        transfer adapter objects.
        """
        return partial(
            getattr(self, name), organization=organization, repo=repo
        )


class PreAuthorizingTransferAdapter(TransferAdapter, ABC):
    """A transfer adapter that can pre-authorize one or more of the
    actions it supports.
    """

    @abstractmethod
    def __init__(self) -> None:
        #
        # These were class attributes, but at least _auth_module ought to
        # be an instance attribute instead.
        #
        self.VERIFY_LIFETIME = 12 * 60 * 60  # Can be quite a while
        if not hasattr(self, "_auth_module"):
            self._auth_module: Authentication | None = None

    def set_auth_module(self, auth_module: Authentication) -> None:
        self._auth_module = auth_module

    @property
    def _preauth_handler_and_identity(
        self,
    ) -> tuple[PreAuthorizedActionAuthenticator | None, Identity | None]:
        if (
            self._auth_module is None
            or self._auth_module.preauth_handler is None
        ):
            return None, None
        handler = cast(
            PreAuthorizedActionAuthenticator, self._auth_module.preauth_handler
        )
        identity = self._auth_module.get_identity()
        return handler, identity

    @property
    def _provides_preauth(self) -> bool:
        return None not in self._preauth_handler_and_identity

    def _preauth_url(
        self,
        original_url: str,
        org: str,
        repo: str,
        actions: set[str] | None = None,
        oid: str | None = None,
        lifetime: int | None = None,
    ) -> str:
        handler, identity = self._preauth_handler_and_identity
        if handler is None or identity is None:
            return original_url

        params = handler.get_authz_query_params(
            identity, org, repo, actions, oid, lifetime=lifetime
        )

        return add_query_params(original_url, params)

    def _preauth_headers(
        self,
        org: str,
        repo: str,
        actions: set[str] | None = None,
        oid: str | None = None,
        lifetime: int | None = None,
    ) -> dict[str, str]:
        handler, identity = self._preauth_handler_and_identity
        if handler is None or identity is None:
            return {}

        return handler.get_authz_header(
            identity, org, repo, actions, oid, lifetime=lifetime
        )


def init_flask_app(app: Flask) -> None:
    """Initialize a flask app instance with transfer adapters.

    This will:
    - Instantiate all transfer adapters defined in config
    - Register any Flask views provided by these adapters
    """
    config = app.config.get("TRANSFER_ADAPTERS", {})
    adapters = {k: _init_adapter(v) for k, v in config.items()}
    for k, adapter in adapters.items():
        register_adapter(k, adapter)

    for adapter in (
        a for a in _registered_adapters.values() if isinstance(a, ViewProvider)
    ):
        adapter.register_views(app)


def register_adapter(key: str, adapter: TransferAdapter) -> None:
    """Register a transfer adapter."""
    _registered_adapters[key] = adapter


def match_transfer_adapter(
    transfers: list[str],
) -> tuple[str, TransferAdapter]:
    """Select a transfer adapter by key."""
    for t in transfers:
        if t in _registered_adapters:
            return t, _registered_adapters[t]
    raise ValueError(f"Unable to match any transfer adapter: {transfers}")


def _init_adapter(config: dict) -> TransferAdapter:
    """Call adapter factory to create a transfer adapter instance."""
    factory: Callable[..., TransferAdapter] = get_callable(config["factory"])
    adapter: TransferAdapter = factory(**config.get("options", {}))
    if isinstance(adapter, PreAuthorizingTransferAdapter):
        adapter.set_auth_module(authentication)
    return adapter
