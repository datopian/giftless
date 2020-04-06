from datetime import datetime, timedelta

import flask
import jwt
import pytest
import pytz

from giftless.auth import Unauthorized
from giftless.auth.jwt import JWTAuthenticator, Scope

# Key used in tests
JWT_KEY = b'some-random-secret'


def test_jwt_can_authorize_request(app):
    """Test basic JWT authorizer functionality
    """
    authz = JWTAuthenticator(private_key=JWT_KEY, algorithm='HS256')
    token = _get_test_token()
    with app.test_request_context('/myorg/myrepo/objects/batch', method='POST', headers={
        "Authorization": f'Bearer {token}'
    }):
        identity = authz(flask.request)
    assert identity.id == 'some-user-id'


def test_jwt_with_wrong_kid_doesnt_authorize_request(app):
    """JWT authorizer only considers a JWT token if it has the right key ID in the header
    """
    authz = JWTAuthenticator(private_key=JWT_KEY, algorithm='HS256', key_id='must-be-this-key')
    token = _get_test_token()
    with app.test_request_context('/myorg/myrepo/objects/batch', method='POST', headers={
        "Authorization": f'Bearer {token}'
    }):
        identity = authz(flask.request)
    assert None is identity


def test_jwt_expired_throws_401(app):
    """If we get a JWT token who's expired, we should raise a 401 error
    """
    authz = JWTAuthenticator(private_key=JWT_KEY, algorithm='HS256')
    token = _get_test_token(lifetime=-600)  # expired 10 minutes ago
    with app.test_request_context('/myorg/myrepo/objects/batch', method='POST', headers={
        "Authorization": f'Bearer {token}'
    }):
        with pytest.raises(Unauthorized):
            authz(flask.request)


def _get_test_token(lifetime=300, headers=None, **kwargs):
    payload = {"exp": datetime.now(tz=pytz.utc) + timedelta(seconds=lifetime),
               "sub": 'some-user-id'}

    payload.update(kwargs)
    return jwt.encode(payload, JWT_KEY, algorithm='HS256', headers=headers).decode('utf8')


@pytest.mark.parametrize('scope_str, expected', [
    ('org:myorg:*', {'entity_type': 'org', 'entity_ref': 'myorg', 'actions': None, 'subscope': None}),
    ('org:myorg', {'entity_type': 'org', 'entity_ref': 'myorg', 'actions': None, 'subscope': None}),
    ('ds', {'entity_type': 'ds', 'entity_ref': None, 'actions': None, 'subscope': None}),
    ('ds:*', {'entity_type': 'ds', 'entity_ref': None, 'actions': None, 'subscope': None}),
    ('ds:*:read', {'entity_type': 'ds', 'entity_ref': None, 'actions': {'read'}, 'subscope': None}),
    ('ds:foobaz:meta:read', {'entity_type': 'ds', 'entity_ref': 'foobaz', 'actions': {'read'}, 'subscope': 'meta'}),
    ('ds:foobaz:*:read', {'entity_type': 'ds', 'entity_ref': 'foobaz', 'actions': {'read'}, 'subscope': None}),
    ('ds:foobaz:meta:*', {'entity_type': 'ds', 'entity_ref': 'foobaz', 'actions': None, 'subscope': 'meta'}),
    ('ds:foobaz:delete', {'entity_type': 'ds', 'entity_ref': 'foobaz', 'actions': {'delete'}, 'subscope': None}),
    ('ds:foobaz:create,delete', {'entity_type': 'ds', 'entity_ref': 'foobaz', 'actions': {'create', 'delete'},
                                 'subscope': None}),

])
def test_scope_parsing(scope_str, expected):
    """Test scope string parsing works as expected
    """
    scope = Scope.from_string(scope_str)
    for k, v in expected.items():
        assert getattr(scope, k) == v


@pytest.mark.parametrize('scope, expected', [
    (Scope('org', 'myorg'), 'org:myorg'),
    (Scope('org', 'myorg', subscope='meta'), 'org:myorg:meta:*'),
    (Scope('ds'), 'ds'),
    (Scope('ds', 'foobaz', {'read'}), 'ds:foobaz:read'),
    (Scope('ds', 'foobaz', {'read'}, 'meta'), 'ds:foobaz:meta:read'),
    (Scope('ds', actions={'read'}, subscope='meta'), 'ds:*:meta:read'),
    (Scope('ds', actions={'read', 'write'}, subscope='meta'), 'ds:*:meta:read,write'),
])
def test_scope_stringify(scope, expected):
    """Test scope stringification works as expected
    """
    assert expected == str(scope)
