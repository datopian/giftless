"""Unit tests for auth.github module."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import shuffle
from time import sleep
from typing import Any

import pytest
from marshmallow.exceptions import ValidationError

import giftless.auth.github as gh
from giftless.auth.identity import Permission


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
DEFAULT_USER_ARGS = (
    "kingofthebritons",
    "123456",
    "arthur",
    "arthur@camelot.gov.uk",
)
ZERO_CACHE_CONFIG = gh.CacheConfig(
    user_max_size=0,
    token_max_size=0,
    auth_max_size=0,
    # deliberately non-zero to not get rejected on setting by the timeout logic
    auth_write_ttl=60.0,
    auth_other_ttl=30.0,
)


def test_github_identity_core() -> None:
    user_dict = {
        "login": "kingofthebritons",
        "id": "123456",
        "name": "arthur",
        "email": "arthur@camelot.gov.uk",
        "other_field": "other_value",
    }
    cache_cfg = DEFAULT_CONFIG.cache
    user = gh.GithubIdentity.from_dict(user_dict, cc=cache_cfg)
    assert (user.login, user.id, user.name, user.email) == DEFAULT_USER_ARGS
    assert all(arg in repr(user) for arg in DEFAULT_USER_ARGS[:3])
    assert hash(user) == hash((user.login, user.id))

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
    org, repo = "org", "repo"
    assert not user.is_authorized(org, repo, Permission.READ_META)
    user.authorize(org, repo, {Permission.READ_META, Permission.READ})
    assert user.permissions(org, repo) == {
        Permission.READ_META,
        Permission.READ,
    }
    assert user.is_authorized(org, repo, Permission.READ_META)
    assert user.is_authorized(org, repo, Permission.READ)
    assert not user.is_authorized(org, repo, Permission.WRITE)


def test_github_identity_authorization_proxy_cache_only() -> None:
    user = gh.GithubIdentity(*DEFAULT_USER_ARGS, cc=ZERO_CACHE_CONFIG)
    org, repo, repo2 = "org", "repo", "repo2"
    user.authorize(org, repo, Permission.all())
    user.authorize(org, repo2, Permission.all())
    assert user.is_authorized(org, repo, Permission.READ_META)
    # without cache, the authorization expires after 1st is_authorized
    assert not user.is_authorized(org, repo, Permission.READ_META)
    assert user.is_authorized(org, repo2, Permission.READ_META)
    assert not user.is_authorized(org, repo2, Permission.READ_META)
