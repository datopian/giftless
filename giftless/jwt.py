"""JWT handling module

This module is used for two purposes:

1. A JWTHandler instance can be used as an authenticator module to authenticate
*any* request to Giftless, as long as it contains a properly signed and valid
JWT token

2. A JWTHandler instance can be used to provide JWT tokens for batch API
"actions", if the client needs to perform a follow-up request to Giftless
"""
from datetime import datetime, timedelta
from functools import partial
from typing import Optional

import jwt

from giftless.authentication import Unauthorized, authentication


class JWT:

    _handler = None

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        if not app.config.get('JWT', {}).get('enabled', False):
            # TODO: register some mock instance that will do nothing
            return

        JWT._handler = JWTHandler(**app.config['JWT'].get('options', {}))
        authentication.push_authenticator(partial(self._handler.authenticate))

    @classmethod
    def token(cls, *args, **kwargs) -> Optional[str]:
        """Access the singleton instance of the handler to generate a JWT token

        TODO: this whole global instance thing is a bit ugly but for now it's the only
              way I could get it to work with Flask. Need to revise at some point.
        """
        if cls._handler is None:
            return None
        return cls._handler.generate_token(*args, **kwargs).decode('utf8')


class JWTHandler:

    DEFAULT_ALGORITHM = 'HS256'
    DEFAULT_LIFETIME = 300
    DEFAULT_LEEWAY = 10

    def __init__(self, secret_key: str, lifetime: int = DEFAULT_LIFETIME, algorithm: str = DEFAULT_ALGORITHM,
                 public_key: Optional[str] = None, issuer: Optional[str] = None, audience: Optional[str] = None,
                 leeway: int = DEFAULT_LEEWAY):
        self.algorithm = algorithm
        self.lifetime = lifetime
        self.leeway = leeway
        self.secret_key = secret_key
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience

    def authenticate(self, request):
        """Authenticate a request
        """
        token = self._get_token(request)
        if token is None:
            return None

        # Check if this is a JWT token
        try:
            jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None

        # We got a JWT token, now let's decode and verify it
        try:
            return jwt.decode(token, key=self.secret_key, algorithms=self.algorithm, leeway=self.leeway)
        except jwt.PyJWTError:
            raise Unauthorized('Expired or otherwise invalid JWT token')

    def generate_token(self, subject: str) -> bytes:
        """Generate a JWT token that can be used later to authenticate a request
        """
        payload = {"exp": datetime.now() + timedelta(seconds=self.lifetime),
                   "sub": subject}
        if self.issuer:
            payload['iss'] = self.issuer
        if self.audience:
            payload['aud'] = self.audience

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def _get_token(self, request) -> Optional[str]:
        """Extract JWT token from request
        """
        header: str = request.headers.get('Authorization')
        if not header:
            return None

        try:
            authz_type, payload = header.split(" ", 1)
        except ValueError:
            return None

        if authz_type.lower() != 'bearer':
            return None

        return payload
