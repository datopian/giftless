"""Unit tests for auth.github module."""
import base64
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from random import shuffle
from time import sleep
from typing import Any, cast

import cachetools.keys
import flask
import pytest
import requests
import responses
from marshmallow.exceptions import ValidationError

import giftless.auth.github as gh
from giftless.auth import Unauthorized
from giftless.auth.github import GithubAppIdentity
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


def test_config_schema_api_timeout() -> None:
    with pytest.raises(ValidationError):
        _config = gh.Config.from_dict({"api_timeout": "invalid"})
    cfg = gh.Config.from_dict({"api_timeout": 1})
    assert cfg.api_timeout == 1.0
    cfg = gh.Config.from_dict({"api_timeout": [1, 2]})
    assert cfg.api_timeout == (1.0, 2.0)
    with pytest.raises(ValidationError):
        _config = gh.Config.from_dict({"api_timeout": [1, "invalid"]})


DEFAULT_CONFIG = gh.Config.from_dict({})
DEFAULT_USER_DICT = {
    "login": "kingofthebritons",
    "id": "125678",
    "name": "arthur",
    "email": "arthur@camelot.gov.uk",
}
DEFAULT_USER_ARGS = tuple(DEFAULT_USER_DICT.values())
ZERO_CACHE_CONFIG = gh.CacheConfig(
    token_max_size=0,
    auth_max_size=0,
    # deliberately non-zero to not get rejected on setting by the timeout logic
    auth_write_ttl=60.0,
    auth_other_ttl=30.0,
)
ORG = "my-org"
REPO = "my-repo"

DEFAULT_ORG_ACCOUNT = {
    "login": ORG,
    "id": 12345678,
}
DEFAULT_SEL_ID = 123
DEFAULT_SEL_CLIENT_ID = "Iv1.4f5cb2a91609a823"
DEFAULT_SEL_APP_ID = 123456
DEFAULT_SEL_APP_SLUG = "app-with-selected-repos"
DEFAULT_ALL_ID = 456
DEFAULT_ALL_CLIENT_ID = "Iv23liEtURKGAMtEbGUy"
DEFAULT_ALL_APP_ID = 456123
DEFAULT_ALL_APP_SLUG = "app-with-all-repos"
DEFAULT_APP_TOKEN = "ghs_tCnvkxzE2v7DgEE45fCGnMMbFLNO8T19EVAH"
DEFAULT_ORG_INSTALLATIONS = {
    "total_count": 2,
    "installations": [
        {
            "id": DEFAULT_SEL_ID,
            "client_id": DEFAULT_SEL_CLIENT_ID,
            "account": DEFAULT_ORG_ACCOUNT,
            "repository_selection": "selected",
            "app_id": DEFAULT_SEL_APP_ID,
            "app_slug": DEFAULT_SEL_APP_SLUG,
            "target_id": DEFAULT_ORG_ACCOUNT["id"],
            "target_type": "Organization",
            "permissions": {"contents": "read", "metadata": "read"},
        },
        {
            "id": DEFAULT_ALL_ID,
            "client_id": DEFAULT_ALL_CLIENT_ID,
            "account": DEFAULT_ORG_ACCOUNT,
            "repository_selection": "all",
            "app_id": DEFAULT_ALL_APP_ID,
            "app_slug": DEFAULT_ALL_APP_SLUG,
            "target_id": DEFAULT_ORG_ACCOUNT["id"],
            "target_type": "Organization",
            "permissions": {
                "organization_administration": "read",
                "contents": "read",
                "metadata": "read",
            },
        },
    ],
}

DEFAULT_INSTALLATION_REPO = {
    "id": 123456789,
    "name": REPO,
    "full_name": f"{ORG}/{REPO}",
    "owner": DEFAULT_ORG_ACCOUNT,
}


def test_github_user_identity_core() -> None:
    # use some value to get filtered out
    user_data = DEFAULT_USER_DICT | {"other_field": "other_value"}
    cache_cfg = DEFAULT_CONFIG.cache
    core_identity = gh.GithubUserIdentity.CoreIdentity.from_user_data(
        user_data
    )
    user = gh.GithubUserIdentity(core_identity, user_data, cache_cfg)
    assert (user.id, user.github_id, user.name, user.email) == tuple(
        DEFAULT_USER_DICT.values()
    )

    assert user.cache_ttl({Permission.WRITE}) == cache_cfg.auth_write_ttl
    assert (
        user.cache_ttl({Permission.READ_META, Permission.READ})
        == cache_cfg.auth_other_ttl
    )


def test_github_identity_authorization_cache() -> None:
    core_identity = gh.GithubUserIdentity.CoreIdentity.from_user_data(
        DEFAULT_USER_DICT
    )
    user = gh.GithubUserIdentity(
        core_identity, DEFAULT_USER_DICT, DEFAULT_CONFIG.cache
    )
    assert not user.is_authorized(ORG, REPO, Permission.READ_META)
    user._set_permissions(ORG, REPO, {Permission.READ_META, Permission.READ})
    assert user._permissions(ORG, REPO) == {
        Permission.READ_META,
        Permission.READ,
    }
    assert user.is_authorized(ORG, REPO, Permission.READ_META)
    assert user.is_authorized(ORG, REPO, Permission.READ)
    assert not user.is_authorized(ORG, REPO, Permission.WRITE)


def test_github_identity_authorization_proxy_cache_only() -> None:
    core_identity = gh.GithubUserIdentity.CoreIdentity.from_user_data(
        DEFAULT_USER_DICT
    )
    user = gh.GithubUserIdentity(
        core_identity, DEFAULT_USER_DICT, ZERO_CACHE_CONFIG
    )
    org, repo, repo2 = ORG, REPO, "repo2"
    user._set_permissions(org, repo, Permission.all())
    user._set_permissions(org, repo2, Permission.all())
    assert user.is_authorized(org, repo, Permission.READ_META)
    # without cache, the authorization expires after 1st is_authorized
    assert not user.is_authorized(org, repo, Permission.READ_META)
    assert user.is_authorized(org, repo2, Permission.READ_META)
    assert not user.is_authorized(org, repo2, Permission.READ_META)


def auth_request_context(
    app: flask.Flask,
    org: str = ORG,
    repo: str = REPO,
    req_auth_header: str | None = "",
    user: str = "token",
    token: str = "dummy-github-token",
) -> flask.ctx.RequestContext:
    if req_auth_header is None:
        headers = None
    elif req_auth_header == "":
        # default - token
        basic_auth = base64.b64encode(
            b":".join([user.encode(), token.encode()])
        ).decode()
        headers = {"Authorization": f"Basic {basic_auth}"}
    else:
        headers = {"Authorization": req_auth_header}

    return app.test_request_context(
        f"/{org}/{repo}.git/info/lfs/objects/batch",
        method="POST",
        headers=headers,
    )


def auth_request(
    app: flask.Flask,
    auth: gh.GithubAuthenticator,
    *args: Any,
    **kwargs: Any,
) -> Identity | None:
    with auth_request_context(app, *args, **kwargs):
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


def mock_org_installations(
    api_url: str,
    org: str = ORG,
    *args: Any,
    **kwargs: Any,
) -> responses.BaseResponse:
    ret = responses.get(
        f"{api_url}/orgs/{org}/installations",
        *args,
        **kwargs,
    )
    return cast(responses.BaseResponse, ret)


def installation_repo_data(
    repos: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if repos is None:
        repos = [DEFAULT_INSTALLATION_REPO]
    return {
        "total_count": len(repos),
        "repository_selection": "selected",
        "repositories": repos,
    }


def mock_installation_repos(
    api_url: str,
    *args: Any,
    **kwargs: Any,
) -> responses.BaseResponse:
    ret = responses.get(
        f"{api_url}/installation/repositories",
        *args,
        **kwargs,
    )
    return cast(responses.BaseResponse, ret)


def test_call_context_restrict_to_org_only(app: flask.Flask) -> None:
    cfg = gh.Config.from_dict({"restrict_to": {ORG: None}})
    with auth_request_context(app):
        ctx = gh.CallContext(cfg, flask.request)
        assert ctx is not None
    with auth_request_context(app, org="bogus"):
        with pytest.raises(Unauthorized):
            gh.CallContext(cfg, flask.request)


def test_call_context_restrict_to_org_and_repo(app: flask.Flask) -> None:
    cfg = gh.Config.from_dict({"restrict_to": {ORG: [REPO]}})
    with auth_request_context(app):
        ctx = gh.CallContext(cfg, flask.request)
        assert ctx is not None
    with auth_request_context(app, repo="bogus"):
        with pytest.raises(Unauthorized):
            gh.CallContext(cfg, flask.request)


def test_call_context_api_get_no_session(app: flask.Flask) -> None:
    with auth_request_context(app):
        ctx = gh.CallContext(DEFAULT_CONFIG, flask.request)
    with pytest.raises(RuntimeError):
        ctx.api_get("/dummy")


def test_call_context_api_get_paginated_no_session(app: flask.Flask) -> None:
    with auth_request_context(app):
        ctx = gh.CallContext(DEFAULT_CONFIG, flask.request)
    with pytest.raises(RuntimeError):
        next(ctx.api_get_paginated("/dummy"))


@responses.activate
def test_call_context_api_get_paginated_per_page_min_max(
    app: flask.Flask,
) -> None:
    uri = "/items"
    response_url = f"{DEFAULT_CONFIG.api_url}{uri}"
    response_data = {"items": [{"item": 1}]}
    resp_min = responses.get(
        response_url,
        match=[
            responses.matchers.query_param_matcher(
                # desired params in the request
                {"per_page": 1},
                strict_match=False,
            )
        ],
        json=response_data,
    )
    resp_max = responses.get(
        response_url,
        match=[
            responses.matchers.query_param_matcher(
                {"per_page": 100}, strict_match=False
            )
        ],
        json=response_data,
    )
    with auth_request_context(app):
        with gh.CallContext(DEFAULT_CONFIG, flask.request) as ctx:
            next(ctx.api_get_paginated(uri, per_page=0))
            next(ctx.api_get_paginated(uri, per_page=101))
    assert resp_min.call_count == 1
    assert resp_max.call_count == 1


@responses.activate
def test_call_context_api_get_paginated_list_name(app: flask.Flask) -> None:
    one_item = {"item": 1}
    items = {"items": [one_item]}
    uri_matching = "/items"
    url_matching = f"{DEFAULT_CONFIG.api_url}{uri_matching}"
    responses.get(url_matching, json=items)
    uri_not_matching = "/nomatch"
    url_not_matching = f"{DEFAULT_CONFIG.api_url}{uri_not_matching}"
    responses.get(url_not_matching, json=items)
    uri_explicit_matching = "/explicit-match"
    url_explicit_matching = f"{DEFAULT_CONFIG.api_url}{uri_explicit_matching}"
    responses.get(url_explicit_matching, json=items)

    with auth_request_context(app):
        with gh.CallContext(DEFAULT_CONFIG, flask.request) as ctx:
            # verify getting one item works
            paginated_gen = ctx.api_get_paginated(uri_matching, per_page=1)
            out_item = next(paginated_gen)
            assert out_item == one_item
            # verify the iteration ends properly
            with pytest.raises(StopIteration):
                next(paginated_gen)
            # verify the iteration without match ends immediately
            with pytest.raises(StopIteration):
                next(ctx.api_get_paginated(uri_not_matching, per_page=1))
            # verify the explicitly matching entry works again
            out_item = next(
                ctx.api_get_paginated(
                    uri_explicit_matching, per_page=1, list_name="items"
                )
            )
            assert out_item == one_item


@responses.activate
def test_call_context_api_get_paginated_link(app: flask.Flask) -> None:
    one_item = {"item": 1}
    other_item = {"item": 2}
    uri = "/items"
    url = f"{DEFAULT_CONFIG.api_url}{uri}"
    # return first page with a link to the second
    resp_1 = responses.get(
        url,
        match=[
            responses.matchers.query_param_matcher(
                {"page": 1}, strict_match=False
            )
        ],
        json={"items": [one_item]},
        headers={"link": f'<{url}?page=2>; rel="next"'},
    )
    # return second page with a link to the third (which is bad)
    resp_2 = responses.get(
        url,
        match=[
            responses.matchers.query_param_matcher(
                {"page": 2}, strict_match=False
            )
        ],
        json={"items": [other_item]},
        headers={"link": f'<{url}?page=3>; rel="next"'},
    )
    resp_3 = responses.get(
        url,
        match=[
            responses.matchers.query_param_matcher(
                {"page": 3}, strict_match=False
            )
        ],
        json={"error": "not found"},
        status=404,
    )

    with auth_request_context(app):
        with gh.CallContext(DEFAULT_CONFIG, flask.request) as ctx:
            # verify reading the first page works
            paginated_gen = ctx.api_get_paginated(uri, per_page=1)
            out_item = next(paginated_gen)
            assert out_item == one_item
            # verify reading the second page works
            out_item = next(paginated_gen)
            assert out_item == other_item
            # verify the bad iteration
            with pytest.raises(requests.exceptions.RequestException):
                next(paginated_gen)
    assert resp_1.call_count == 1
    assert resp_2.call_count == 1
    assert resp_3.call_count == 1


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


@responses.activate
def test_github_auth_request_cache_no_leak(app: flask.Flask) -> None:
    auth = gh.factory(cache={"token_max_size": 2})
    user_resp = mock_user(auth, json=DEFAULT_USER_DICT)
    perm_resp = mock_perm(auth, json={"permission": "admin"})

    # authenticate 1st token, check it got cached properly
    token1 = "token-1"
    token1_cache_key = cachetools.keys.hashkey(token1)
    identity1 = auth_request(app, auth, token=token1)
    assert isinstance(identity1, gh.GithubUserIdentity)
    assert len(auth._token_cache) == 1
    assert token1_cache_key in auth._token_cache
    assert len(gh.GithubUserIdentity._cached_users) == 1
    assert any(
        i is identity1 for i in gh.GithubUserIdentity._cached_users.values()
    )
    # see both the authentication and authorization requests took place
    assert user_resp.call_count == 1
    assert perm_resp.call_count == 1
    # remove local strong reference
    del identity1

    # authenticate the same user with different token (fill cache)
    token2 = "token-2"
    token2_cache_key = cachetools.keys.hashkey(token2)
    identity2 = auth_request(app, auth, token=token2)
    assert len(auth._token_cache) == 2
    assert token2_cache_key in auth._token_cache
    assert len(gh.GithubUserIdentity._cached_users) == 1
    assert any(
        i is identity2 for i in gh.GithubUserIdentity._cached_users.values()
    )
    # see only the authentication request took place
    assert user_resp.call_count == 2
    assert perm_resp.call_count == 1
    del identity2

    # authenticate once more (cache will evict oldest)
    token3 = "token-3"
    token3_cache_key = cachetools.keys.hashkey(token3)
    identity3 = auth_request(app, auth, token=token3)
    assert len(auth._token_cache) == 2
    assert token3_cache_key in auth._token_cache
    assert token1_cache_key not in auth._token_cache
    assert len(gh.GithubUserIdentity._cached_users) == 1
    assert any(
        i is identity3 for i in gh.GithubUserIdentity._cached_users.values()
    )
    # see only the authentication request took place
    assert user_resp.call_count == 3
    assert perm_resp.call_count == 1
    del identity3

    # evict 2nd cached token
    del auth._token_cache[token2_cache_key]
    assert len(auth._token_cache) == 1
    assert len(gh.GithubUserIdentity._cached_users) == 1
    # evict 3rd
    del auth._token_cache[token3_cache_key]
    assert len(auth._token_cache) == 0
    assert len(gh.GithubUserIdentity._cached_users) == 0

    # try once more with 1st token
    auth_request(app, auth, token=token1)
    assert len(auth._token_cache) == 1
    assert len(gh.GithubUserIdentity._cached_users) == 1
    # see both the authentication and authorization requests took place
    assert user_resp.call_count == 4
    assert perm_resp.call_count == 2


@responses.activate
def test_github_auth_request_app_no_user(app: flask.Flask) -> None:
    auth = gh.factory()
    mock_org_installations(auth.api_url, json=DEFAULT_ORG_INSTALLATIONS)

    with pytest.raises(Unauthorized):
        auth_request(app, auth, user="", token=DEFAULT_APP_TOKEN)


@responses.activate
def test_github_auth_request_app_bad_user(app: flask.Flask) -> None:
    auth = gh.factory()
    mock_org_installations(auth.api_url, json=DEFAULT_ORG_INSTALLATIONS)

    with pytest.raises(Unauthorized):
        auth_request(app, auth, token=DEFAULT_APP_TOKEN)


@responses.activate
def test_github_auth_request_app_all_repos(app: flask.Flask) -> None:
    auth = gh.factory(cache={"token_max_size": 0})
    resp = mock_org_installations(auth.api_url, json=DEFAULT_ORG_INSTALLATIONS)

    # match for installation id
    identity_0 = auth_request(
        app, auth, user=str(DEFAULT_ALL_ID), token=DEFAULT_APP_TOKEN
    )
    assert identity_0 is not None
    assert identity_0.is_authorized(ORG, REPO, Permission.READ)
    assert not identity_0.is_authorized(ORG, REPO, Permission.WRITE)
    # match for app_id
    identity = auth_request(
        app, auth, user=str(DEFAULT_ALL_APP_ID), token=DEFAULT_APP_TOKEN
    )
    assert identity == identity_0
    # match for client_id
    identity = auth_request(
        app, auth, user=DEFAULT_ALL_CLIENT_ID, token=DEFAULT_APP_TOKEN
    )
    assert identity == identity_0
    # match for client_id
    identity = auth_request(
        app, auth, user=DEFAULT_ALL_APP_SLUG, token=DEFAULT_APP_TOKEN
    )
    assert identity == identity_0

    assert resp.call_count == 4


@responses.activate
def test_github_auth_request_app_no_org_access(app: flask.Flask) -> None:
    auth = gh.factory(cache={"token_max_size": 0})
    resp = mock_org_installations(
        auth.api_url, json={"error": "Insufficient access rights."}, status=403
    )
    with pytest.raises(Unauthorized):
        auth_request(app, auth, token=DEFAULT_APP_TOKEN)
    assert resp.call_count == 1


@responses.activate
def test_github_auth_request_app_reauth(app: flask.Flask) -> None:
    auth = gh.factory(cache={"auth_max_size": 0})
    resp = mock_org_installations(auth.api_url, json=DEFAULT_ORG_INSTALLATIONS)
    identity = auth_request(
        app, auth, user=str(DEFAULT_ALL_ID), token=DEFAULT_APP_TOKEN
    )
    assert identity is not None
    assert identity.is_authorized(ORG, REPO, Permission.READ)
    # the authorization shouldn't be cached
    identity = auth_request(app, auth, token=DEFAULT_APP_TOKEN)
    assert identity is not None
    assert identity.is_authorized(ORG, REPO, Permission.READ)

    assert resp.call_count == 2


@responses.activate
def test_github_auth_request_app_selected_repos(app: flask.Flask) -> None:
    auth = gh.factory(cache={"token_max_size": 0})
    resp_i = mock_org_installations(
        auth.api_url, json=DEFAULT_ORG_INSTALLATIONS
    )
    resp_r = mock_installation_repos(
        auth.api_url, json=installation_repo_data()
    )

    identity = auth_request(
        app, auth, user=str(DEFAULT_SEL_ID), token=DEFAULT_APP_TOKEN
    )
    assert identity is not None
    assert identity.is_authorized(ORG, REPO, Permission.READ)
    assert resp_i.call_count == 1
    assert resp_r.call_count == 1


@responses.activate
def test_github_auth_request_app_selected_repos_no_match(
    app: flask.Flask,
) -> None:
    auth = gh.factory(cache={"auth_max_size": 2})  # one gets casually cached
    no_match_repo_1 = DEFAULT_INSTALLATION_REPO.copy()
    no_match_repo_1_name = "no-match-1"
    no_match_repo_1["name"] = no_match_repo_1_name
    no_match_repo_2 = DEFAULT_INSTALLATION_REPO.copy()
    no_match_repo_2["name"] = "no-match-2"
    no_match_repos = [no_match_repo_1, no_match_repo_2]
    mock_org_installations(auth.api_url, json=DEFAULT_ORG_INSTALLATIONS)
    resp_r = mock_installation_repos(
        auth.api_url, json=installation_repo_data(no_match_repos)
    )

    identity = auth_request(
        app, auth, user=str(DEFAULT_SEL_ID), token=DEFAULT_APP_TOKEN
    )
    assert identity is not None
    assert resp_r.call_count == 1
    assert not identity.is_authorized(ORG, REPO, Permission.READ)
    assert identity.is_authorized(ORG, no_match_repo_1_name, Permission.READ)


@responses.activate
def test_github_auth_request_app_selected_repos_no_access(
    app: flask.Flask,
) -> None:
    auth = gh.factory()
    mock_org_installations(auth.api_url, json=DEFAULT_ORG_INSTALLATIONS)
    resp_r = mock_installation_repos(
        auth.api_url, json={"error": "Insufficient access rights."}, status=403
    )

    with pytest.raises(Unauthorized):
        auth_request(
            app, auth, user=str(DEFAULT_SEL_ID), token=DEFAULT_APP_TOKEN
        )

    assert resp_r.call_count == 1


@responses.activate
def test_github_auth_request_app_selected_repos_bad_authorize(
    app: flask.Flask,
) -> None:
    mock_org_installations(
        DEFAULT_CONFIG.api_url, json=DEFAULT_ORG_INSTALLATIONS
    )
    with auth_request_context(
        app, user=str(DEFAULT_SEL_ID), token=DEFAULT_APP_TOKEN
    ):
        with gh.CallContext(DEFAULT_CONFIG, flask.request) as ctx:
            identity = GithubAppIdentity.authenticate(ctx)
            ctx.org = "whoops"
            with pytest.raises(RuntimeError):
                identity.authorize(ctx)


@responses.activate
def test_github_auth_request_app_missing_permissions(app: flask.Flask) -> None:
    auth = gh.factory()
    no_perm = deepcopy(DEFAULT_ORG_INSTALLATIONS)
    inst = next(
        _i
        for _i in cast(list, no_perm["installations"])
        if _i["id"] == DEFAULT_SEL_ID
    )
    del inst["permissions"]
    resp_i = mock_org_installations(auth.api_url, json=no_perm)

    with pytest.raises(Unauthorized):
        auth_request(
            app, auth, user=str(DEFAULT_SEL_ID), token=DEFAULT_APP_TOKEN
        )
    assert resp_i.call_count == 1


@responses.activate
def test_github_auth_request_app_missing_permissions_contents(
    app: flask.Flask,
) -> None:
    auth = gh.factory()
    no_perm = deepcopy(DEFAULT_ORG_INSTALLATIONS)
    inst = next(
        _i
        for _i in cast(list, no_perm["installations"])
        if _i["id"] == DEFAULT_SEL_ID
    )
    del inst["permissions"]["contents"]
    resp_i = mock_org_installations(auth.api_url, json=no_perm)

    with pytest.raises(Unauthorized):
        auth_request(
            app, auth, user=str(DEFAULT_SEL_ID), token=DEFAULT_APP_TOKEN
        )
    assert resp_i.call_count == 1


@responses.activate
def test_github_auth_request_app_write_permissions(app: flask.Flask) -> None:
    auth = gh.factory()
    no_perm = deepcopy(DEFAULT_ORG_INSTALLATIONS)
    inst = next(
        _i
        for _i in cast(list, no_perm["installations"])
        if _i["id"] == DEFAULT_ALL_ID
    )
    inst["permissions"]["contents"] = "write"
    resp_i = mock_org_installations(auth.api_url, json=no_perm)

    identity = auth_request(
        app, auth, user=str(DEFAULT_ALL_ID), token=DEFAULT_APP_TOKEN
    )
    assert identity is not None
    assert identity.is_authorized(ORG, REPO, Permission.WRITE)
    assert resp_i.call_count == 1


@responses.activate
def test_github_auth_request_app_unknown_permissions(app: flask.Flask) -> None:
    auth = gh.factory()
    no_perm = deepcopy(DEFAULT_ORG_INSTALLATIONS)
    inst = next(
        _i
        for _i in cast(list, no_perm["installations"])
        if _i["id"] == DEFAULT_ALL_ID
    )
    inst["permissions"]["contents"] = "twist"
    resp_i = mock_org_installations(auth.api_url, json=no_perm)

    with pytest.raises(Unauthorized):
        auth_request(
            app, auth, user=str(DEFAULT_ALL_ID), token=DEFAULT_APP_TOKEN
        )
    assert resp_i.call_count == 1
