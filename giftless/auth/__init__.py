"""Abstract authentication and authorization layer."""
import abc
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from flask import Flask, Request, current_app, g
from flask import request as flask_request
from typing_extensions import Protocol
from werkzeug.exceptions import Unauthorized as BaseUnauthorized

from giftless.util import get_callable

from . import allow_anon  # noqa: F401
from .identity import Identity

# We'll use the Werkzeug exception for Unauthorized, but encapsulate it
Unauthorized = BaseUnauthorized


# Type for "Authenticator"
# This can probably be made more specific once our protocol is more clear
# TODO @athornton: can it?
class Authenticator(Protocol):
    """Authenticators are callables (an object or function) that can
    authenticate a request and provide an identity object.
    """

    def __call__(self, request: Request) -> Identity | None:
        raise NotImplementedError(
            "This is a protocol definition;"
            " it should not be called directly."
        )


class PreAuthorizedActionAuthenticator(abc.ABC):
    """Pre-authorized action authenticators are special authenticators
    that can also pre-authorize a follow-up action to the Git LFS
    server.

    They serve to both pre-authorize Git LFS actions and check these
    actions are authorized as they come in.
    """

    @abc.abstractmethod
    def get_authz_query_params(
        self,
        identity: Identity,
        org: str,
        repo: str,
        actions: set[str] | None = None,
        oid: str | None = None,
        lifetime: int | None = None,
    ) -> dict[str, str]:
        """Authorize an action by adding credentials to the query string."""

    @abc.abstractmethod
    def get_authz_header(
        self,
        identity: Identity,
        org: str,
        repo: str,
        actions: set[str] | None = None,
        oid: str | None = None,
        lifetime: int | None = None,
    ) -> dict[str, str]:
        """Authorize an action by adding credentials to the request headers."""


class Authentication:
    """Wrap multiple Authenticators and default behaviors into an object to
    manage authentication flow.
    """

    def __init__(
        self,
        app: Flask | None = None,
        default_identity: Identity | None = None,
    ) -> None:
        self._default_identity = default_identity
        self._authenticators: list[Authenticator] | None = None
        self._unauthorized_handler: Callable | None = None
        self.preauth_handler: Authenticator | None = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the Flask app."""
        app.config.setdefault("AUTH_PROVIDERS", [])
        app.config.setdefault("PRE_AUTHORIZED_ACTION_PROVIDER", None)

    def get_identity(self) -> Identity | None:
        if hasattr(g, "user") and isinstance(g.user, Identity):
            return g.user

        log = logging.getLogger(__name__)
        g.user = self._authenticate()
        if g.user:
            log.debug("Authenticated identity: %s", g.user)
            return g.user

        log.debug("No authenticated identity could be found")
        return None

    def login_required(self, f: Callable) -> Callable:
        """Decorate the view; a typical Flask "login_required"."""

        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            user = self.get_identity()
            if not user:
                return self.auth_failure()
            return f(*args, **kwargs)

        return decorated_function

    def no_identity_handler(self, f: Callable) -> Callable:
        """Marker decorator for "unauthorized handler" function.

        This function will be called automatically if no authenticated
        identity was found but is required.
        """
        self._unauthorized_handler = f

        @wraps(f)
        def decorated_func(*args: Any, **kwargs: Any) -> Any:
            return f(*args, **kwargs)

        return decorated_func

    def auth_failure(self) -> Any:
        """Trigger an authentication failure."""
        if self._unauthorized_handler:
            return self._unauthorized_handler()
        else:
            raise Unauthorized("User identity is required")

    def init_authenticators(self, reload: bool = False) -> None:
        """Register an authenticator function."""
        if reload:
            self._authenticators = None

        if self._authenticators:
            return

        log = logging.getLogger(__name__)
        log.debug(
            "Initializing authenticators,"
            f" have {len(current_app.config['AUTH_PROVIDERS'])}"
            " authenticator(s) configured"
        )

        self._authenticators = [
            _create_authenticator(a)
            for a in current_app.config["AUTH_PROVIDERS"]
        ]

        if current_app.config["PRE_AUTHORIZED_ACTION_PROVIDER"]:
            log.debug("Initializing pre-authorized action provider")
            self.preauth_handler = _create_authenticator(
                current_app.config["PRE_AUTHORIZED_ACTION_PROVIDER"]
            )
            self.push_authenticator(self.preauth_handler)

    def push_authenticator(self, authenticator: Authenticator) -> None:
        """Push an authenticator at the top of the stack."""
        if self._authenticators is None:
            self._authenticators = [authenticator]
            return
        self._authenticators.insert(0, authenticator)

    def _authenticate(self) -> Identity | None:
        """Call all registered authenticators until we find an identity."""
        self.init_authenticators()
        if self._authenticators is None:
            return self._default_identity
        for authn in self._authenticators:
            try:
                current_identity = authn(flask_request)
                if current_identity is not None:
                    return current_identity
            except Unauthorized as e:  # noqa:PERF203
                # An authenticator is telling us the provided identity is
                # invalid, so we should stop looking and return "no identity"
                log = logging.getLogger(__name__)
                log.debug(e.description)
                return None

        return self._default_identity


def _create_authenticator(spec: str | dict[str, Any]) -> Authenticator:
    """Instantiate an authenticator from configuration spec.

    Configuration spec can be a string referencing a callable
    (e.g. mypackage.mymodule:callable) in which case the callable will
    be returned as is; Or, a dict with 'factory' and 'options' keys,
    in which case the factory callable is called with 'options' passed
    in as argument, and the resulting callable is returned.
    """
    log = logging.getLogger(__name__)

    if isinstance(spec, str):
        log.debug(f"Creating authenticator: {spec}")
        return get_callable(spec, __name__)

    log.debug(f"Creating authenticator using factory: {spec['factory']}")
    factory = get_callable(spec["factory"], __name__)
    options = spec.get("options", {})
    return cast(Authenticator, factory(**options))


authentication = Authentication()
