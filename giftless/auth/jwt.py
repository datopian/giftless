from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt

from giftless.auth import PreAuthorizedActionAuthenticator, Unauthorized
from giftless.auth.identity import DefaultIdentity, Identity


class JWTAuthenticator(PreAuthorizedActionAuthenticator):

    DEFAULT_ALGORITHM = 'HS256'
    DEFAULT_LIFETIME = 300
    DEFAULT_LEEWAY = 10

    def __init__(self, private_key: str, lifetime: int = DEFAULT_LIFETIME, algorithm: str = DEFAULT_ALGORITHM,
                 public_key: Optional[str] = None, issuer: Optional[str] = None, audience: Optional[str] = None,
                 leeway: int = DEFAULT_LEEWAY, key_id: Optional[str] = None):
        self.algorithm = algorithm
        self.lifetime = lifetime
        self.leeway = leeway
        self.private_key = private_key
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience
        self.key_id = key_id

    def __call__(self, request: Any) -> Optional[Identity]:
        token_payload = self._authenticate(request)
        if token_payload is None:
            return None
        return DefaultIdentity()

    def authorize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return action

    # def _sign_actions(self, adapter: TransferAdapter, object: Dict[str, Any]):
    #     """Sign object actions using JWT token if we need to and JWT is configured
    #     """
    #     if not adapter.presign_actions:
    #         return object
    #
    #     for action_name, action_spec in object['actions'].items():
    #         if action_name in adapter.presign_actions:
    #             headers = action_spec.get('header', {})
    #             if 'Authorization' in headers or 'authorization' in headers:
    #                 continue
    #
    #             token = JWT.token('foobaz')
    #             if token is None:
    #                 continue
    #
    #             headers['Authorization'] = f'Bearer {token}'
    #             action_spec['header'] = headers
    #             action_spec['expires_in'] = JWT.lifetime()
    #
    #     object['authenticated'] = True
    #
    #     return object

    def generate_token(self, subject: str) -> bytes:
        """Generate a JWT token that can be used later to authenticate a request
        """
        payload = {"exp": datetime.now() + timedelta(seconds=self.lifetime),
                   "sub": subject}

        if self.issuer:
            payload['iss'] = self.issuer

        if self.audience:
            payload['aud'] = self.audience

        headers = {}
        if self.key_id:
            headers['kid'] = self.key_id

        return jwt.encode(payload, self.private_key, algorithm=self.algorithm, headers=headers)

    def _authenticate(self, request):
        """Authenticate a request
        """
        token = self._get_token(request)
        if token is None:
            return None

        # Check if this is a JWT token, and if it has the expected key ID
        try:
            header = jwt.get_unverified_header(token)
            if self.key_id and self.key_id != header.get('kid'):
                return None
        except jwt.PyJWTError:
            return None

        # We got a JWT token, now let's decode and verify it
        try:
            return jwt.decode(token, key=self.private_key, algorithms=self.algorithm, leeway=self.leeway)
        except jwt.PyJWTError:
            raise Unauthorized('Expired or otherwise invalid JWT token')

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


def factory(**options):
    for key_type in ('private_key', 'public_key'):
        file_opt = f'{key_type}_file'
        try:
            if options[file_opt]:
                with open(options[file_opt]) as f:
                    options[key_type] = f.read()
            options.pop(file_opt)
        except KeyError:
            continue

    return JWTAuthenticator(**options)
