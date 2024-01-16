"""Tests for JWT authorization."""
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import flask
import jwt
import pytest

from giftless.auth import Unauthorized
from giftless.auth.identity import DefaultIdentity, Permission
from giftless.auth.jwt import JWTAuthenticator, Scope, factory

# Symmetric key used in tests
JWT_HS_KEY = b"some-random-secret"

# Asymmetric key files used in tests
JWT_RS_PRI_KEY = Path(__file__).parent / "data" / "test-key.pem"
JWT_RS_PUB_KEY = Path(__file__).parent / "data" / "test-key.pub.pem"


def test_jwt_can_authorize_request_symmetric_key(app: flask.Flask) -> None:
    """Test basic JWT authorizer functionality: HS256 symmetric."""
    authz = JWTAuthenticator(private_key=JWT_HS_KEY, algorithm="HS256")
    token = _get_test_token()
    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    ):
        identity = authz(flask.request)
    assert identity is not None
    assert identity.id == "some-user-id"


def test_jwt_can_authorize_request_asymmetric_key(app: flask.Flask) -> None:
    """Test basic JWT authorizer functionality: RS256 asymmetric."""
    authz = factory(public_key_file=JWT_RS_PUB_KEY, algorithm="RS256")
    token = _get_test_token(algo="RS256")
    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    ):
        identity = authz(flask.request)
    assert identity is not None
    assert identity.id == "some-user-id"


def test_jwt_can_authorize_request_token_in_qs(app: flask.Flask) -> None:
    """Test basic JWT authorizer functionality with query param."""
    authz = JWTAuthenticator(private_key=JWT_HS_KEY, algorithm="HS256")
    token = _get_test_token()
    with app.test_request_context(
        f"/myorg/myrepo/objects/batch?jwt={token}", method="POST"
    ):
        identity = authz(flask.request)
    assert identity is not None
    assert identity.id == "some-user-id"


def test_jwt_can_authorize_request_token_as_basic_password(
    app: flask.Flask,
) -> None:
    """Test that we can pass a JWT token as 'Basic' authorization password."""
    authz = JWTAuthenticator(private_key=JWT_HS_KEY, algorithm="HS256")
    token = _get_test_token()
    auth_value = base64.b64encode(
        b":".join([b"_jwt", token.encode("ascii")])
    ).decode("ascii")

    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Basic {auth_value}"},
    ):
        identity = authz(flask.request)
    assert identity is not None
    assert identity.id == "some-user-id"


def test_jwt_can_authorize_request_token_basic_password_disabled(
    app: flask.Flask,
) -> None:
    """Test that we can pass a JWT token as 'Basic' authorization password
    when user is None.
    """
    authz = JWTAuthenticator(
        private_key=JWT_HS_KEY, algorithm="HS256", basic_auth_user=None
    )
    token = _get_test_token()
    auth_value = base64.b64encode(
        b":".join([b"_jwt", token.encode("ascii")])
    ).decode("ascii")

    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Basic {auth_value}"},
    ):
        identity = authz(flask.request)
    assert identity is None


def test_jwt_with_wrong_kid_doesnt_authorize_request(app: flask.Flask) -> None:
    """JWT authorizer only considers a JWT token if it has the right key ID
    in the header.
    """
    authz = JWTAuthenticator(
        private_key=JWT_HS_KEY, algorithm="HS256", key_id="must-be-this-key"
    )
    token = _get_test_token()
    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    ):
        identity = authz(flask.request)
    assert identity is None


def test_jwt_expired_throws_401(app: flask.Flask) -> None:
    """If we get a JWT token that has expired, we should raise a 401 error."""
    authz = JWTAuthenticator(private_key=JWT_HS_KEY, algorithm="HS256")
    token = _get_test_token(lifetime=-600)  # expired 10 minutes ago
    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    ):
        with pytest.raises(Unauthorized):
            authz(flask.request)


def test_jwt_pre_authorize_action() -> None:
    authz = JWTAuthenticator(
        private_key=JWT_HS_KEY, algorithm="HS256", default_lifetime=120
    )
    identity = DefaultIdentity(
        name="joe", email="joe@shmoe.com", id="babab0ba"
    )
    header = authz.get_authz_header(
        identity, "myorg", "somerepo", actions={"read"}
    )

    auth_type, token = header["Authorization"].split(" ")
    assert auth_type == "Bearer"

    payload = jwt.decode(token, JWT_HS_KEY, algorithms="HS256")
    assert payload["sub"] == "babab0ba"
    assert payload["scopes"] == "obj:myorg/somerepo/*:read"

    # Check that now() - expiration time is within 5 seconds of 120 seconds
    assert (
        abs(
            (
                datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                - datetime.now(tz=timezone.utc)
            ).seconds
            - 120
        )
        < 5
    )


def test_jwt_pre_authorize_action_custom_lifetime() -> None:
    authz = JWTAuthenticator(
        private_key=JWT_HS_KEY, algorithm="HS256", default_lifetime=120
    )
    identity = DefaultIdentity(
        name="joe", email="joe@shmoe.com", id="babab0ba"
    )
    header = authz.get_authz_header(
        identity, "myorg", "somerepo", actions={"read"}, lifetime=3600
    )

    auth_type, token = header["Authorization"].split(" ")
    assert auth_type == "Bearer"

    payload = jwt.decode(token, JWT_HS_KEY, algorithms="HS256")
    assert payload["sub"] == "babab0ba"
    assert payload["scopes"] == "obj:myorg/somerepo/*:read"

    # Check that now() - expiration time is within 5 seconds of 3600 seconds
    assert (
        abs(
            (
                datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                - datetime.now(tz=timezone.utc)
            ).seconds
            - 3600
        )
        < 5
    )


@pytest.mark.parametrize(
    ("scopes", "auth_check", "expected"),
    [
        (
            [],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            ["blah:foo/bar:*"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            ["obj:myorg/myrepo/*"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            True,
        ),
        (
            ["obj:myorg/myrepo/*"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.WRITE,
            },
            True,
        ),
        (
            ["obj:myorg/otherrepo/*"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            ["obj:myorg/myrepo/*:read"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.WRITE,
            },
            False,
        ),
        (
            ["obj:myorg/myrepo/*:write"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.WRITE,
            },
            True,
        ),
        (
            ["obj:myorg/myrepo/*:read,write"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.WRITE,
            },
            True,
        ),
        (
            ["obj:myorg/myrepo/*:read,verify"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ_META,
            },
            True,
        ),
        (
            ["obj:myorg/myrepo/*:read"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ_META,
            },
            True,
        ),
        (
            ["obj:myorg/myrepo/*:meta:*"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ_META,
            },
            True,
        ),
        (
            ["obj:myorg/myrepo/*:meta:read,write,verify"],
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            "obj:myorg/myrepo/*:meta:*",
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ_META,
            },
            True,
        ),
        (
            "obj:myorg/*/*:read",
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            True,
        ),
        (
            "obj:myorg/*/*:read",
            {
                "organization": "otherorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            "obj:myorg/*/*:read",
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.WRITE,
            },
            False,
        ),
        (
            "obj:*/*/*:read",
            {
                "organization": "myorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            True,
        ),
        (
            "obj:*/*/*:read",
            {
                "organization": "otherorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            True,
        ),
        (
            "obj:*/*/someobjectid:read",
            {
                "organization": "otherorg",
                "repo": "myrepo",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            "obj:*/*/someobjectid:read",
            {
                "organization": "otherorg",
                "repo": "myrepo",
                "oid": "someobjectid",
                "permission": Permission.READ,
            },
            True,
        ),
        (
            "obj:*/*/someobjectid:read",
            {
                "organization": "otherorg",
                "repo": "myrepo",
                "oid": "otherobjectid",
                "permission": Permission.READ,
            },
            False,
        ),
        (
            "obj:someobjectid:read",
            {
                "organization": "myorg",
                "repo": "anonrelatedrepo",
                "oid": "someobjectid",
                "permission": Permission.READ,
            },
            True,
        ),
    ],
)
def test_jwt_scopes_authorize_actions(
    app: flask.Flask, scopes: str, auth_check: dict[str, Any], expected: bool
) -> None:
    """Test that JWT token scopes can control authorization."""
    authz = JWTAuthenticator(private_key=JWT_HS_KEY, algorithm="HS256")
    token = _get_test_token(scopes=scopes)
    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    ):
        identity = authz(flask.request)

    assert identity is not None
    assert identity.is_authorized(**auth_check) is expected


def test_jwt_scopes_authorize_actions_with_anon_user(app: flask.Flask) -> None:
    """Test that authorization works even if we don't have any user ID
    / email / name.
    """
    scopes = ["obj:myorg/myrepo/*"]
    authz = JWTAuthenticator(private_key=JWT_HS_KEY, algorithm="HS256")
    token = _get_test_token(scopes=scopes, sub=None, name=None, email=None)
    with app.test_request_context(
        "/myorg/myrepo/objects/batch",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    ):
        identity = authz(flask.request)

    assert identity is not None
    assert identity.is_authorized(
        organization="myorg", repo="myrepo", permission=Permission.READ
    )


@pytest.mark.parametrize(
    ("scope_str", "expected"),
    [
        (
            "org:myorg:*",
            {
                "entity_type": "org",
                "entity_ref": "myorg",
                "actions": None,
                "subscope": None,
            },
        ),
        (
            "org:myorg",
            {
                "entity_type": "org",
                "entity_ref": "myorg",
                "actions": None,
                "subscope": None,
            },
        ),
        (
            "ds",
            {
                "entity_type": "ds",
                "entity_ref": None,
                "actions": None,
                "subscope": None,
            },
        ),
        (
            "ds:*",
            {
                "entity_type": "ds",
                "entity_ref": None,
                "actions": None,
                "subscope": None,
            },
        ),
        (
            "ds:*:read",
            {
                "entity_type": "ds",
                "entity_ref": None,
                "actions": {"read"},
                "subscope": None,
            },
        ),
        (
            "ds:foobaz:meta:read",
            {
                "entity_type": "ds",
                "entity_ref": "foobaz",
                "actions": {"read"},
                "subscope": "meta",
            },
        ),
        (
            "ds:foobaz:*:read",
            {
                "entity_type": "ds",
                "entity_ref": "foobaz",
                "actions": {"read"},
                "subscope": None,
            },
        ),
        (
            "ds:foobaz:meta:*",
            {
                "entity_type": "ds",
                "entity_ref": "foobaz",
                "actions": None,
                "subscope": "meta",
            },
        ),
        (
            "ds:foobaz:delete",
            {
                "entity_type": "ds",
                "entity_ref": "foobaz",
                "actions": {"delete"},
                "subscope": None,
            },
        ),
        (
            "ds:foobaz:create,delete",
            {
                "entity_type": "ds",
                "entity_ref": "foobaz",
                "actions": {"create", "delete"},
                "subscope": None,
            },
        ),
    ],
)
def test_scope_parsing(scope_str: str, expected: dict[str, Any]) -> None:
    """Test scope string parsing works as expected."""
    scope = Scope.from_string(scope_str)
    for k, v in expected.items():
        assert getattr(scope, k) == v


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (Scope("org", "myorg"), "org:myorg"),
        (Scope("org", "myorg", subscope="meta"), "org:myorg:meta:*"),
        (Scope("ds"), "ds"),
        (Scope("ds", "foobaz", {"read"}), "ds:foobaz:read"),
        (Scope("ds", "foobaz", {"read"}, "meta"), "ds:foobaz:meta:read"),
        (Scope("ds", actions={"read"}, subscope="meta"), "ds:*:meta:read"),
        (
            Scope("ds", actions={"read", "write"}, subscope="meta"),
            "ds:*:meta:read,write",
        ),
    ],
)
def test_scope_stringify(scope: Scope, expected: str) -> None:
    """Test scope stringification works as expected."""
    assert expected == str(scope)


def _get_test_token(
    lifetime: int = 300,
    headers: dict[str, Any] | None = None,
    algo: str = "HS256",
    **kwargs: Any,
) -> str:
    payload = {
        "exp": datetime.now(tz=timezone.utc) + timedelta(seconds=lifetime),
        "sub": "some-user-id",
    }

    payload.update(kwargs)

    if algo == "HS256":
        key = JWT_HS_KEY
    elif algo == "RS256":
        with JWT_RS_PRI_KEY.open("rb") as f:
            key = f.read()
    else:
        raise ValueError(f"Don't know how to test algo: {algo}")

    token = jwt.encode(payload, key, algorithm=algo, headers=headers)
    # Type of jwt.encode() went from bytes to str in jwt 2.x, but the
    # typing hints somehow aren't keeping up.  This lets us do the
    # right thing with jwt 2.x.
    if isinstance(token, str):  # type: ignore[unreachable]
        return token  # type: ignore[unreachable]
    return token.decode("ascii")
