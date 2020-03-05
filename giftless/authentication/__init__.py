"""Abstract authentication for Flask
"""
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from flask import current_app, g, request
from werkzeug.exceptions import Unauthorized as BaseUnauthorized

from giftless.util import get_callable

from .dummy import authenticate as dummy_authenticator  # noqa: F401

# Types for "Authenticator" callable and "Identity"
# This can probably be made more specific once our protocol is more clear
Identity = Optional[Any]
Authenticator = Callable[[Any], Identity]

# We'll use the Werkzeug exception for Unauthorized, but encapsulate it
Unauthorized = BaseUnauthorized


class Authentication:

    def __init__(self, app=None, default_identity: Identity = None):
        self._default_identity = default_identity
        self._authenticators: List[Authenticator] = []
        self._unauthorized_handler: Optional[Callable] = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the Flask app
        """
        app.config.setdefault('AUTHENTICATORS', [])

    def get_identity(self) -> Identity:
        if not hasattr(g, 'user') or g.user is None:
            g.user = self._authenticate()
        return g.user

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

        self._authenticators = [_create_authenticator(a) for a in current_app.config['AUTHENTICATORS']]

    def _authenticate(self) -> Identity:
        """Call all registered authenticators until we find an identity
        """
        self.init_authenticators()
        for authn in self._authenticators:
            try:
                identity = authn(request)
                if identity is not None:
                    return identity
            except Unauthorized:
                # An authenticator is telling us the provided identity is invalid
                # We should stop looking and return "no identity"
                return None

        return self._default_identity


def _create_authenticator(spec: Union[str, Dict[str, Any]]) -> Authenticator:
    """Instantiate an authenticator from configuration spec

    Configuration spec can be a string referencing a callable (e.g. mypackage.mymodule:callable)
    in which case the callable will be returned as is; Or, a dict with 'factory' and 'options'
    keys, in which case the factory callable is called with 'options' passed in as argument, and
    the resulting callable is returned.
    """
    if isinstance(spec, str):
        return get_callable(spec, __name__)

    factory = get_callable(spec['factory'], __name__)  # type: Callable[..., Authenticator]
    options = spec.get('options', {})
    return factory(**options)


authentication = Authentication()
