"""Unit tests for auth.github module."""
import base64
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import shuffle
from time import sleep
from typing import Any, cast

import flask
import pytest
import responses
from marshmallow.exceptions import ValidationError

import giftless.auth.github as gh
from giftless.auth import Unauthorized
from giftless.auth.identity import Identity, Permission


def test_ensure_default_lock() -> None:
    lock_getter = gh._ensure_lock()
    lock = lock_getter(None)
    with lock:
        # Is it a RLock or just Lock?
        if lock.acquire(blocking=False):
            lock.release()


def _concurrent_side_effects(
    decorator: Callable[[Callable[..., Any]], Any],
    thread_cnt: int = 4,
    exception: type[Exception] | None = None,
) -> tuple[list, list, list]:
    @decorator
    def decorated_method(_ignored_self: Any, index: int) -> int:
        sleep(0.1)
        side_effects[index] = index
        if exception is not None:
            raise exception(index)
        return index

    results: list[int | None] = [None] * thread_cnt
    side_effects: list[int | None] = [None] * thread_cnt
    exceptions: list[Exception | None] = [None] * thread_cnt

    with ThreadPoolExecutor(
        max_workers=thread_cnt, thread_name_prefix="scm-"
    ) as executor:
        thread_indices = list(range(thread_cnt))
        shuffle(thread_indices)
        futures = {
            executor.submit(decorated_method, i, i): i for i in thread_indices
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                exceptions[i] = exc
            else:
                results[i] = result

    return results, side_effects, exceptions


def test_single_call_method_decorator_default_no_args() -> None:
    decorator = gh.single_call_method
    results, side_effects, exceptions = _concurrent_side_effects(decorator)
    # the differing index (taken into account by default) breaks call coupling,
    # so this decoration has no effect and all calls get through
    assert results == side_effects


def test_single_call_method_decorator_default_args() -> None:
    decorator = gh.single_call_method()
    results, side_effects, exceptions = _concurrent_side_effects(decorator)
    # same as test_single_call_method_decorator_default_no_args, but checking
    # if the decorator factory works properly with no explicit args
    assert results == side_effects


def test_single_call_method_decorator_default_exception() -> None:
    decorator = gh.single_call_method()
    results, side_effects, exceptions = _concurrent_side_effects(
        decorator, exception=Exception
    )
    # same as test_single_call_method_decorator_default_no_args, but checking
    # if the decorator factory works properly with no explicit args
    assert all(r is None for r in results)
    assert all(se is not None for se in side_effects)
    assert all(e is not None for e in exceptions)


def test_single_call_method_decorator_call_once() -> None:
    # using a constant hash key to put all threads in the same bucket
    decorator = gh.single_call_method(key=lambda *args: 0)
    threads = 4
    results, side_effects, exceptions = _concurrent_side_effects(
        decorator, threads
    )
    assert all(e is None for e in exceptions)
    # as there's just a sleep in the decorated_method, technically multiple
    # threads could enter the method call (and thus produce side_effects),
    # but the expectation is the sleep is long enough for all to get stuck
    chosen_ones = [se for se in side_effects if se is not None]
    # at least one thread got stuck
    assert len(chosen_ones) < threads
    assert all(r in chosen_ones for r in results)


def test_single_call_method_decorator_call_once_exception() -> None:
    # using a constant hash key to put all threads in the same bucket
    decorator = gh.single_call_method(key=lambda *args: 0)
    threads = 4
    results, side_effects, exceptions = _concurrent_side_effects(
        decorator, threads, Exception
    )
    assert all(r is None for r in results)
    assert all(e is not None for e in exceptions)
    chosen_ones = [se for se in side_effects if se is not None]
    # at least one thread got stuck
    assert len(chosen_ones) < threads
    # make sure the exceptions come from the calling thread
    assert all(e.args[0] in chosen_ones for e in exceptions)


def test_cachedmethod_threadsafe_default_key() -> None:
    # cache all the uncoupled calls
    cache: dict[Any, Any] = {}
    threads = 4
    decorator = gh.cachedmethod_threadsafe(lambda _self: cache)
    results, side_effects, exceptions = _concurrent_side_effects(
        decorator, threads
    )
    assert all(e is None for e in exceptions)
    assert results == side_effects
    assert len(cache) == threads


def test_cachedmethod_threadsafe_call_once() -> None:
    # one result ends up cached, even if call produces different results
    # (this is supposed to be used for idempotent methods, so multiple calls
    # are supposed to produce identical results)
    cache: dict[Any, Any] = {}
    decorator = gh.cachedmethod_threadsafe(
        lambda _self: cache, key=lambda *args: 0
    )
    results, side_effects, exceptions = _concurrent_side_effects(decorator)
    assert all(e is None for e in exceptions)
    chosen_ones = [se for se in side_effects if se is not None]
    assert len(cache) == 1
    cached_result = next(iter(cache.values()))
    assert cached_result in chosen_ones


def test_config_schema_defaults() -> None:
    config = gh.Config.from_dict({})
    assert isinstance(config, gh.Config)
    assert hasattr(config, "cache")
    assert isinstance(config.cache, gh.CacheConfig)


def test_config_schema_default_cache() -> None:
    config = gh.Config.from_dict({"cache": {}})
    assert isinstance(config, gh.Config)
    assert hasattr(config, "cache")
    assert isinstance(config.cache, gh.CacheConfig)


def test_config_schema_empty_cache() -> None:
    options = {"cache": None}
    with pytest.raises(ValidationError):
        _config = gh.Config.from_dict(options)


DEFAULT_CONFIG = gh.Config.from_dict({})
DEFAULT_USER_DICT = {
    "login": "kingofthebritons",
    "id": "12345678",
    "name": "arthur",
    "email": "arthur@camelot.gov.uk",
}
DEFAULT_USER_ARGS = tuple(DEFAULT_USER_DICT.values())
ZERO_CACHE_CONFIG = gh.CacheConfig(
    user_max_size=0,
    token_max_size=0,
    auth_max_size=0,
    # deliberately non-zero to not get rejected on setting by the timeout logic
    auth_write_ttl=60.0,
    auth_other_ttl=30.0,
)
ORG = "my-org"
REPO = "my-repo"


def test_github_identity_core() -> None:
    # use some value to get filtered out
    user_dict = DEFAULT_USER_DICT | {"other_field": "other_value"}
    cache_cfg = DEFAULT_CONFIG.cache
    user = gh.GithubIdentity.from_dict(user_dict, cc=cache_cfg)
    assert (user.id, user.github_id, user.name, user.email) == DEFAULT_USER_ARGS
    assert all(arg in repr(user) for arg in DEFAULT_USER_ARGS[:3])
    assert hash(user) == hash((user.id, user.github_id))

    args2 = (*DEFAULT_USER_ARGS[:2], "spammer", "spam@camelot.gov.uk")
    user2 = gh.GithubIdentity(*args2, cc=cache_cfg)
    assert user == user2
    user2.id = "654321"
    assert user != user2

    assert user.cache_ttl({Permission.WRITE}) == cache_cfg.auth_write_ttl
    assert (
        user.cache_ttl({Permission.READ_META, Permission.READ})
        == cache_cfg.auth_other_ttl
    )


def test_github_identity_authorization_cache() -> None:
    user = gh.GithubIdentity(*DEFAULT_USER_ARGS, cc=DEFAULT_CONFIG.cache)
    assert not user.is_authorized(ORG, REPO, Permission.READ_META)
    user.authorize(ORG, REPO, {Permission.READ_META, Permission.READ})
    assert user.permissions(ORG, REPO) == {
        Permission.READ_META,
        Permission.READ,
    }
    assert user.is_authorized(ORG, REPO, Permission.READ_META)
    assert user.is_authorized(ORG, REPO, Permission.READ)
    assert not user.is_authorized(ORG, REPO, Permission.WRITE)


def test_github_identity_authorization_proxy_cache_only() -> None:
    user = gh.GithubIdentity(*DEFAULT_USER_ARGS, cc=ZERO_CACHE_CONFIG)
    org, repo, repo2 = ORG, REPO, "repo2"
    user.authorize(org, repo, Permission.all())
    user.authorize(org, repo2, Permission.all())
    assert user.is_authorized(org, repo, Permission.READ_META)
    # without cache, the authorization expires after 1st is_authorized
    assert not user.is_authorized(org, repo, Permission.READ_META)
    assert user.is_authorized(org, repo2, Permission.READ_META)
    assert not user.is_authorized(org, repo2, Permission.READ_META)


def auth_request(
    app: flask.Flask,
    auth: gh.GithubAuthenticator,
    org: str = ORG,
    repo: str = REPO,
    req_auth_header: str | None = "",
) -> Identity | None:
    if req_auth_header is None:
        headers = None
    elif req_auth_header == "":
        # default - token
        token = "dummy-github-token"
        basic_auth = base64.b64encode(
            b":".join([b"token", token.encode()])
        ).decode()
        headers = {"Authorization": f"Basic {basic_auth}"}
    else:
        headers = {"Authorization": req_auth_header}

    with app.test_request_context(
        f"/{org}/{repo}.git/info/lfs/objects/batch",
        method="POST",
        headers=headers,
    ):
        return auth(flask.request)


def mock_user(
    auth: gh.GithubAuthenticator, *args: Any, **kwargs: Any
) -> responses.BaseResponse:
    ret = responses.get(f"{auth.api_url}/user", *args, **kwargs)
    return cast(responses.BaseResponse, ret)


def mock_perm(
    auth: gh.GithubAuthenticator,
    org: str = ORG,
    repo: str = REPO,
    login: str = DEFAULT_USER_DICT["login"],
    *args: Any,
    **kwargs: Any,
) -> responses.BaseResponse:
    ret = responses.get(
        f"{auth.api_url}/repos/{org}/{repo}/collaborators/{login}/permission",
        *args,
        **kwargs,
    )
    return cast(responses.BaseResponse, ret)


def test_github_auth_request_missing_auth(app: flask.Flask) -> None:
    auth = gh.factory()
    with pytest.raises(Unauthorized):
        auth_request(app, auth, req_auth_header=None)


def test_github_auth_request_funny_auth(app: flask.Flask) -> None:
    auth = gh.factory()
    with pytest.raises(Unauthorized):
        auth_request(app, auth, req_auth_header="Funny key1=val1, key2=val2")


@responses.activate
def test_github_auth_request_bad_user(app: flask.Flask) -> None:
    auth = gh.factory()
    mock_user(auth, json={"error": "Forbidden"}, status=403)
    with pytest.raises(Unauthorized):
        auth_request(app, auth)


@responses.activate
def test_github_auth_request_bad_perm(app: flask.Flask) -> None:
    auth = gh.factory(api_version=None)
    mock_user(auth, json=DEFAULT_USER_DICT)
    mock_perm(auth, json={"error": "Forbidden"}, status=403)

    with pytest.raises(Unauthorized):
        auth_request(app, auth)


@responses.activate
def test_github_auth_request_admin(app: flask.Flask) -> None:
    auth = gh.factory()
    mock_user(auth, json=DEFAULT_USER_DICT)
    mock_perm(auth, json={"permission": "admin"})

    identity = auth_request(app, auth)
    assert identity is not None
    assert identity.is_authorized(ORG, REPO, Permission.WRITE)


@responses.activate
def test_github_auth_request_read(app: flask.Flask) -> None:
    auth = gh.factory()
    mock_user(auth, json=DEFAULT_USER_DICT)
    mock_perm(auth, json={"permission": "read"})

    identity = auth_request(app, auth)
    assert identity is not None
    assert not identity.is_authorized(ORG, REPO, Permission.WRITE)
    assert identity.is_authorized(ORG, REPO, Permission.READ)


@responses.activate
def test_github_auth_request_none(app: flask.Flask) -> None:
    auth = gh.factory()
    mock_user(auth, json=DEFAULT_USER_DICT)
    mock_perm(auth, json={"permission": "none"})

    identity = auth_request(app, auth)
    assert identity is not None
    assert not identity.is_authorized(ORG, REPO, Permission.WRITE)
    assert not identity.is_authorized(ORG, REPO, Permission.READ)


@responses.activate
def test_github_auth_request_cached(app: flask.Flask) -> None:
    auth = gh.factory()
    user_resp = mock_user(auth, json=DEFAULT_USER_DICT)
    perm_resp = mock_perm(auth, json={"permission": "admin"})

    auth_request(app, auth)
    # second cached call
    identity = auth_request(app, auth)
    assert identity is not None
    assert identity.is_authorized(ORG, REPO, Permission.WRITE)
    assert user_resp.call_count == 1
    assert perm_resp.call_count == 1
