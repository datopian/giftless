import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set, Union

import jwt
from dateutil.tz import UTC
from flask import Request
from werkzeug.http import parse_authorization_header

from giftless.auth import PreAuthorizedActionAuthenticator, Unauthorized
from giftless.auth.identity import DefaultIdentity, Identity, Permission
from giftless.util import to_iterable


class JWTAuthenticator(PreAuthorizedActionAuthenticator):
    """Default JWT based authenticator

    This authenticator authenticates users by accepting a well-formed JWT token
    (in the Authorization header as a Bearer type token). Tokens must be signed
    by the right key, and also match in terms of audience, issuer and key ID if
    configured, and of course have valid course expiry / not before times.

    Beyond authentication, JWT tokens may also include authorization payload
    in the "scopes" claim.

    Multiple scope strings can be provided, and are expected to have the
    following structure:

        obj:{org}/{repo}/{oid}:{subscope}:{actions}

    or:

        obj:{org}/{repo}/{oid}:{actions}

    Where:

        {org} is the organization of the target object

        {repo} is the repository of the target object. Omitting or replacing
               with '*' designates we are granting access to all repositories
               in the organization

        {oid} is the Object ID. Omitting or replacing with '*' designates we
              are granting access to all objects in the repository

        {subscope} can be 'metadata' or omitted entirely. If 'metadata' is
                   specified, the scope does not grant access to actual files,
                   but to metadata only - e.g. objects can be verified to exist
                   but not downloaded.

        {actions} is a comma separated list of allowed actions. Actions can be
                  'read', 'write' or 'verify'. If omitted or replaced with a
                  '*', all actions are permitted.

    Some examples of decoded tokens (added comments are not valid JSON):

        {
          "exp": 1586253890,           // Token expiry time
          "sub": "a-users-id",         // Optional user ID
          "iat": 1586253590,           // Optional, issued at
          "nbf": 1586253590,           // Optional, not valid before
          "name": "User Name",         // Optional, user's name
          "email": "user@example.com", // Optional, user's email
          "scopes": [
            // read a specific object
            "obj:datopian/somerepo/6adada03e86b154be00e25f288fcadc27aef06c47f12f88e3e1985c502803d1b:read",

            // read the same object, but do not limit to a specific prefix
            "obj:6adada03e86b154be00e25f288fcadc27aef06c47f12f88e3e1985c502803d1b:read",

            // full access to all objects in a repo
            "obj:datopian/my-repo/*",

            // Read only access to all repositories for an organization
            "obj:datopian/*:read",

            // Metadata read only access to all objects in a repository
            "obj:datopian/my-repo:meta:verify",
          ]
        }

    Typically a token will include a single scope - but multiple scopes are
    allowed.

    This authenticator will pass on the attempt to authenticate if no token was
    provided, or it is not a JWT token, or if a key ID is configured and a
    provided JWT token does not have the matching "kid" head claim (this allows
    chaining multiple JWT authenticators if needed).

    However, if a matching but invalid token was provided, a 401 Unauthorized
    response will be returned. "Invalid" means a token with audience or issuer
    mismatch (if configured), an expiry time in the past or an "not before"
    time in the future, or, of course, an invalid signature.

    The "leeway" parameter allows for providing a leeway / grace time to be
    considered when checking expiry times, to cover for clock skew between
    servers.
    """
    DEFAULT_ALGORITHM = 'HS256'
    DEFAULT_LIFETIME = 60
    DEFAULT_LEEWAY = 10
    DEFAULT_BASIC_AUTH_USER = '_jwt'

    def __init__(self, private_key: Optional[Union[str, bytes]] = None, default_lifetime: int = DEFAULT_LIFETIME,
                 algorithm: str = DEFAULT_ALGORITHM, public_key: Optional[str] = None, issuer: Optional[str] = None,
                 audience: Optional[str] = None, leeway: int = DEFAULT_LEEWAY, key_id: Optional[str] = None,
                 basic_auth_user: Optional[str] = DEFAULT_BASIC_AUTH_USER):
        self.algorithm = algorithm
        self.default_lifetime = default_lifetime
        self.leeway = leeway
        self.private_key = private_key
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience
        self.key_id = key_id
        self.basic_auth_user = basic_auth_user
        self._verification_key: Union[str, bytes, None] = None  # lazy loaded
        self._log = logging.getLogger(__name__)

    def __call__(self, request: Request) -> Optional[Identity]:
        token_payload = self._authenticate(request)
        if token_payload is None:
            return None
        return self._get_identity(token_payload)

    def get_authz_header(self, *args, **kwargs) -> Dict[str, str]:
        token = self._generate_token_for_action(*args, **kwargs)
        return {'Authorization': f'Bearer {token}'}

    def get_authz_query_params(self, *args, **kwargs) -> Dict[str, str]:
        return {'jwt': self._generate_token_for_action(*args, **kwargs)}

    def _generate_token_for_action(self, identity: Identity, org: str, repo: str, actions: Optional[Set[str]] = None,
                                   oid: Optional[str] = None, lifetime: Optional[int] = None) -> str:
        """Generate a JWT token authorizing the specific requested action
        """
        token_payload: Dict[str, Any] = {"sub": identity.id}
        if self.issuer:
            token_payload['iss'] = self.issuer
        if self.audience:
            token_payload['aud'] = self.audience
        if identity.email:
            token_payload['email'] = identity.email
        if identity.name:
            token_payload['name'] = identity.name

        # Scopes
        token_payload['scopes'] = self._generate_action_scopes(org, repo, actions, oid)

        # Custom lifetime
        if lifetime:
            token_payload['exp'] = datetime.now(tz=UTC) + timedelta(seconds=lifetime)

        return self._generate_token(**token_payload).decode('ascii')

    @staticmethod
    def _generate_action_scopes(org: str, repo: str, actions: Optional[Set[str]] = None, oid: Optional[str] = None) \
            -> str:
        """Generate token scopes based on target object and actions
        """
        if oid is None:
            oid = '*'
        obj_id = f'{org}/{repo}/{oid}'
        return str(Scope('obj', obj_id, actions))

    def _generate_token(self, **kwargs) -> bytes:
        """Generate a JWT token that can be used later to authenticate a request
        """
        if not self.private_key:
            raise ValueError("This authenticator is not configured to generate tokens; Set private_key to fix")

        payload: Dict[str, Any] = {
            "exp": datetime.now(tz=UTC) + timedelta(seconds=self.default_lifetime),
            "iat": datetime.now(tz=UTC),
            "nbf": datetime.now(tz=UTC)
        }

        payload.update(**kwargs)

        if self.issuer:
            payload['iss'] = self.issuer

        if self.audience:
            payload['aud'] = self.audience

        headers = {}
        if self.key_id:
            headers['kid'] = self.key_id

        return jwt.encode(payload, self.private_key, algorithm=self.algorithm, headers=headers)  # type: ignore

    def _authenticate(self, request: Request):
        """Authenticate a request
        """
        token = self._get_token_from_headers(request)
        if token is None:
            token = self._get_token_from_qs(request)
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
            return jwt.decode(token, key=self._get_verification_key(), algorithms=self.algorithm, leeway=self.leeway)
        except jwt.PyJWTError as e:
            raise Unauthorized('Expired or otherwise invalid JWT token ({})'.format(str(e)))

    def _get_token_from_headers(self, request: Request) -> Optional[str]:
        """Extract JWT token from HTTP Authorization header

        This will first try to obtain a Bearer token. If none is found but we have a 'Basic' Authorization header,
        and basic auth JWT payload has not been disabled, and the provided username matches the configured JWT token
        username, we will try to use the provided password as if it was a JWT token.
        """
        header = request.headers.get('Authorization')
        if not header:
            return None

        try:
            authz_type, payload = header.split(" ", 1)
        except ValueError:
            return None

        if authz_type.lower() == 'bearer':
            self._log.debug("Found token in Authorization: Bearer header")
            return payload
        elif authz_type.lower() == 'basic' and self.basic_auth_user:
            parsed_header = parse_authorization_header(header)
            if parsed_header and parsed_header.username == self.basic_auth_user:
                self._log.debug("Found token in Authorization: Basic header")
                return parsed_header.password

        return None

    @staticmethod
    def _get_token_from_qs(request: Request) -> Optional[str]:
        """Get JWT token from the query string
        """
        return request.args.get('jwt')

    def _get_identity(self, jwt_payload: Dict[str, Any]) -> Identity:
        identity = DefaultIdentity(id=jwt_payload.get('sub'),
                                   email=jwt_payload.get('email'),
                                   name=jwt_payload.get('name', jwt_payload.get('sub')))

        scopes = to_iterable(jwt_payload.get('scopes', ()))
        self._log.debug("Allowing scopes: %s", scopes)
        for scope in scopes:
            identity.allow(**self._parse_scope(scope))

        return identity

    def _parse_scope(self, scope_str: str) -> Dict[str, Any]:
        """Parse a scope string and convert it into arguments for Identity.allow()
        """
        scope = Scope.from_string(scope_str)
        if scope.entity_type != 'obj':
            return {}

        organization = None
        repo = None
        oid = None

        if scope.entity_ref is not None:
            id_parts = [p if p != '*' else None for p in scope.entity_ref.split('/', maxsplit=2)]
            if len(id_parts) == 3:
                organization, repo, oid = id_parts
            elif len(id_parts) == 2:
                organization, repo = id_parts
            elif len(id_parts) == 1:
                oid = id_parts[0]

        permissions = self._parse_scope_permissions(scope)

        return {"organization": organization,
                "repo": repo,
                "permissions": permissions,
                "oid": oid}

    @staticmethod
    def _parse_scope_permissions(scope: 'Scope') -> Set[Permission]:
        """Extract granted permissions from scope object
        """
        permissions_map = {'read': {Permission.READ, Permission.READ_META},
                           'write': {Permission.WRITE},
                           'verify': {Permission.READ_META}}

        permissions = set()
        if scope.actions:
            for action in scope.actions:
                permissions.update(permissions_map.get(action, set()))
        else:
            permissions = Permission.all()

        if scope.subscope in {'metadata', 'meta'}:
            permissions = permissions.intersection({Permission.READ_META})

        return permissions

    def _get_verification_key(self) -> Union[str, bytes]:
        """Get the key used for token verification, based on algorithm
        """
        if self._verification_key is None:
            if self.algorithm[0:2] == 'HS':
                self._verification_key = self.private_key
            else:
                self._verification_key = self.public_key

        if self._verification_key is None:
            raise ValueError("No private or public key have been set, can't verify requests")

        return self._verification_key


class Scope(object):
    """Scope object
    """

    entity_type = None
    subscope = None
    entity_ref = None
    actions = None

    def __init__(self, entity_type: str, entity_id: Optional[str] = None, actions: Optional[Set[str]] = None,
                 subscope: Optional[str] = None):
        self.entity_type = entity_type
        self.entity_ref = entity_id
        self.actions = actions
        self.subscope = subscope

    def __repr__(self):
        return '<Scope {}>'.format(str(self))

    def __str__(self):
        """Convert scope to a string
        """
        parts = [self.entity_type]
        entity_ref = self.entity_ref if self.entity_ref != '*' else None
        subscobe = self.subscope if self.subscope != '*' else None
        actions = ','.join(sorted(self.actions)) if self.actions and self.actions != '*' else None

        if entity_ref:
            parts.append(entity_ref)
        elif subscobe or actions:
            parts.append('*')

        if subscobe:
            parts.append(subscobe)
            if not actions:
                parts.append('*')

        if actions:
            parts.append(actions)

        return ':'.join(parts)

    @classmethod
    def from_string(cls, scope_str):
        """Create a scope object from string
        """
        parts = scope_str.split(':')
        if len(parts) < 1:
            raise ValueError("Scope string should have at least 1 part")
        scope = cls(parts[0])
        if len(parts) > 1 and parts[1] != '*':
            scope.entity_ref = parts[1]
        if len(parts) == 3 and parts[2] != '*':
            scope.actions = cls._parse_actions(parts[2])
        if len(parts) == 4:
            if parts[2] != '*':
                scope.subscope = parts[2]
            if parts[3] != '*':
                scope.actions = cls._parse_actions(parts[3])

        return scope

    @classmethod
    def _parse_actions(cls, actions_str: str) -> Set[str]:
        if not actions_str:
            return set()
        return set(actions_str.split(','))


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
