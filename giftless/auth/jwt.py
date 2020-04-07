from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set, Union

import jwt
import pytz

from giftless.auth import PreAuthorizedActionAuthenticator, Unauthorized
from giftless.auth.identity import DefaultIdentity, Identity, Permission


class JWTAuthenticator(PreAuthorizedActionAuthenticator):

    DEFAULT_ALGORITHM = 'HS256'
    DEFAULT_LIFETIME = 300
    DEFAULT_LEEWAY = 10

    def __init__(self, private_key: Optional[Union[str, bytes]], lifetime: int = DEFAULT_LIFETIME,
                 algorithm: str = DEFAULT_ALGORITHM, public_key: Optional[str] = None, issuer: Optional[str] = None,
                 audience: Optional[str] = None, leeway: int = DEFAULT_LEEWAY, key_id: Optional[str] = None):
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
        return self._get_identity(token_payload)

    def get_authz_header(self, identity: Identity, org: str, repo: str, actions: Optional[Set[str]] = None,
                         oid: Optional[str] = None) -> Dict[str, str]:
        token_payload = {"sub": identity.id}
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

        token = self._generate_token(**token_payload)
        return {'Authorization': f'Bearer {token.decode("utf8")}'}

    def _generate_action_scopes(self, org: str, repo: str, actions: Optional[Set[str]] = None,
                                oid: Optional[str] = None) -> str:
        """Generate token scopes based on target object and actions
        """
        if oid is None:
            oid = '*'
        obj_id = f'{org}/{repo}/{oid}'
        return str(Scope('obj', obj_id, actions))

    def _generate_token(self, **kwargs) -> bytes:
        """Generate a JWT token that can be used later to authenticate a request
        """
        payload: Dict[str, Any] = {
            "exp": datetime.now(tz=pytz.utc) + timedelta(seconds=self.lifetime),
            "iat": datetime.now(tz=pytz.utc),
            "nbf": datetime.now(tz=pytz.utc)
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
        except jwt.PyJWTError as e:
            raise Unauthorized('Expired or otherwise invalid JWT token ({})'.format(str(e)))

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

    def _get_identity(self, jwt_payload: Dict[str, Any]) -> Identity:
        identity = DefaultIdentity(id=jwt_payload.get('sub'),
                                   email=jwt_payload.get('email'),
                                   name=jwt_payload.get('name', jwt_payload.get('sub')))

        for scope in jwt_payload.get('scopes', ()):
            identity.allow(**self._parse_scope(scope))

        return identity

    def _parse_scope(self, scope_str: str) -> Dict[str, Any]:
        """Parse a scope string and conveet it into arguments for Identity.allow()
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
                organization = id_parts[0]

        permissions = self._parse_scope_permissions(scope)

        return {"organization": organization,
                "repo": repo,
                "permissions": permissions,
                "oid": oid}

    def _parse_scope_permissions(self, scope: 'Scope') -> Set[Permission]:
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
