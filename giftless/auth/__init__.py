"""Abstract authentication and authorization layer
"""
import abc
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Union

from flask import Request, current_app, g
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
class Authenticator(Protocol):
    """Authenticators are callables (an object or function) that can authenticate
    a request and provide an identity object
    """
    def __call__(self, request: Request) -> Optional[Identity]:
        raise NotImplementedError('This is a protocol definition and should not be called directly')


class PreAuthorizedActionAuthenticator(abc.ABC):
    """Pre-authorized action authenticators are special authenticators
    that can also pre-authorize a follow-up action to the Git LFS server

    They serve to both pre-authorize Git LFS actions and check these actions
    are authorized as they come in.
    """
    def get_authz_query_params(self, identity: Identity, org: str, repo: str, actions: Optional[Set[str]] = None,
                               oid: Optional[str] = None, lifetime: Optional[int] = None) -> Dict[str, str]:
        """Authorize an action by adding credientaisl to the query string
        """
        return {}

    def get_authz_header(self, identity: Identity, org: str, repo: str, actions: Optional[Set[str]] = None,
                         oid: Optional[str] = None, lifetime: Optional[int] = None) -> Dict[str, str]:
        """Authorize an action by adding credentials to the request headers
        """
        return {}


class Authentication:

    def __init__(self, app=None, default_identity: Identity = None):
        self._default_identity = default_identity
        self._authenticators: List[Authenticator] = []
        self._unauthorized_handler: Optional[Callable] = None
        self.preauth_handler: Optional[PreAuthorizedActionAuthenticator] = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the Flask app
        """
        app.config.setdefault('AUTH_PROVIDERS', [])
        app.config.setdefault('PRE_AUTHORIZED_ACTION_PROVIDER', None)

    def get_identity(self) -> Optional[Identity]:
        if hasattr(g, 'user') and isinstance(g.user, Identity):
            return g.user

        log = logging.getLogger(__name__)
        g.user = self._authenticate()
        if g.user:
            log.debug("Authenticated identity: %s", g.user)
            return g.user

        log.debug("No authenticated identity could be found")
        return None

    def login_required(self, f):
        """A typical Flask "login_required" view decorator
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = self.get_identity()
            if not user:
                return self.auth_failure()
            return f(*args, **kwargs)
        return decorated_function

    def no_identity_handler(self, f):
        """Marker decorator for "unauthorized handler" function

        This function will be called automatically if no authenticated identity was found
        but is required.
        """
        self._unauthorized_handler = f

        @wraps(f)
        def decorated_func(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated_func

    def auth_failure(self):
        """Trigger an authentication failure
        """
        if self._unauthorized_handler:
            return self._unauthorized_handler()
        else:
            raise Unauthorized("User identity is required")

    def init_authenticators(self, reload=False):
        """Register an authenticator function
        """
        if reload:
            self._authenticators = None

        if self._authenticators:
            return

        log = logging.getLogger(__name__)
        log.debug("Initializing authenticators, have %d authenticator(s) configured",
                  len(current_app.config['AUTH_PROVIDERS']))

        self._authenticators = [_create_authenticator(a) for a in current_app.config['AUTH_PROVIDERS']]

        if current_app.config['PRE_AUTHORIZED_ACTION_PROVIDER']:
            log.debug("Initializing pre-authorized action provider")
            self.preauth_handler = _create_authenticator(current_app.config['PRE_AUTHORIZED_ACTION_PROVIDER'])
            self.push_authenticator(self.preauth_handler)

    def push_authenticator(self, authenticator):
        """Push an authenticator at the top of the stack
        """
        self._authenticators.insert(0, authenticator)

    def _authenticate(self) -> Optional[Identity]:
        """Call all registered authenticators until we find an identity
        """
        self.init_authenticators()
        for authn in self._authenticators:
            try:
                current_identity = authn(flask_request)
                if current_identity is not None:
                    return current_identity
            except Unauthorized as e:
                # An authenticator is telling us the provided identity is invalid
                # We should stop looking and return "no identity"
                log = logging.getLogger(__name__)
                log.debug(e.description)
                return None

        return self._default_identity


def _create_authenticator(spec: Union[str, Dict[str, Any]]) -> Authenticator:
    """Instantiate an authenticator from configuration spec

    Configuration spec can be a string referencing a callable (e.g. mypackage.mymodule:callable)
    in which case the callable will be returned as is; Or, a dict with 'factory' and 'options'
    keys, in which case the factory callable is called with 'options' passed in as argument, and
    the resulting callable is returned.
    """
    log = logging.getLogger(__name__)

    if isinstance(spec, str):
        log.debug("Creating authenticator: %s", spec)
        return get_callable(spec, __name__)

    log.debug("Creating authenticator using factory: %s", spec['factory'])
    factory = get_callable(spec['factory'], __name__)  # type: Callable[..., Authenticator]
    options = spec.get('options', {})
    return factory(**options)


authentication = Authentication()
