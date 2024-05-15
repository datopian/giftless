"""Objects for GitHub "proxy" authentication."""
import dataclasses
import functools
import logging
import math
import os
import threading
import weakref
from collections.abc import Callable, Mapping, MutableMapping
from contextlib import AbstractContextManager, suppress
from operator import attrgetter, itemgetter
from threading import Lock, RLock
from typing import Any, Protocol, TypeVar, cast, overload

import cachetools.keys
import flask
import marshmallow as ma
import marshmallow.validate
import requests

from giftless.auth import Unauthorized
from giftless.auth.identity import Identity, Permission

_logger = logging.getLogger(__name__)


# THREAD SAFE CACHING UTILS
# original type preserving "return type" for the decorators below
_RT = TypeVar("_RT")


class _LockType(AbstractContextManager, Protocol):
    """Generic type for threading.Lock and RLock."""

    def acquire(self, blocking: bool = ..., timeout: float = ...) -> bool:
        ...

    def release(self) -> None:
        ...


@dataclasses.dataclass(kw_only=True)
class SingleCallContext:
    """Thread-safety context for the single_call_method decorator."""

    # reentrant lock guarding a call with particular arguments
    rlock: _LockType = dataclasses.field(default_factory=RLock)
    start_call: bool = True
    result: Any = None
    error: BaseException | None = None


def _ensure_lock(
    existing_lock: Callable[[Any], _LockType] | None = None,
) -> Callable[[Any], _LockType]:
    if existing_lock is None:
        default_lock = RLock()
        return lambda _self: default_lock
    return existing_lock


@overload
def single_call_method(_method: Callable[..., _RT]) -> Callable[..., _RT]:
    ...


@overload
def single_call_method(
    *,
    key: Callable[..., Any] = cachetools.keys.methodkey,
    lock: Callable[[Any], _LockType] | None = None,
) -> Callable[[Callable[..., _RT]], Callable[..., _RT]]:
    ...


def single_call_method(
    _method: Callable[..., _RT] | None = None,
    *,
    key: Callable[..., Any] = cachetools.keys.methodkey,
    lock: Callable[[Any], _LockType] | None = None,
) -> Callable[..., _RT] | Callable[[Callable[..., _RT]], Callable[..., _RT]]:
    """Thread-safe decorator limiting concurrency of an idempotent method call.
    When multiple threads concurrently call the decorated method with the same
    arguments (governed by the 'key' callable argument), only the first one
    will actually call the method. The other threads will block until the call
    completes with a result or an exception. The saved result is then passed on
    to the blocked threads without multiple calls. When the method call raises
    an exception, it is re-raised in each blocked thread.

    This doesn't provide further caching - as soon as the method call is done
    and all the blocked threads are served, the call is free to happen again.

    It's possible to provide a "getter" callable for the lock guarding the main
    call cache, called as 'lock(self)'. There's a built-in lock by default.
    Each concurrent call is then guarded by its own reentrant lock variable.
    """
    lock = _ensure_lock(lock)

    def decorator(method: Callable[..., _RT]) -> Callable[..., _RT]:
        # tracking concurrent calls per method arguments
        concurrent_calls: dict[Any, SingleCallContext] = {}

        @functools.wraps(method)
        def wrapper(self: Any, *args: tuple, **kwargs: dict) -> _RT:
            lck = lock(self)
            k = key(self, *args, **kwargs)
            with lck:
                try:
                    ctx = concurrent_calls[k]
                except KeyError:
                    concurrent_calls[k] = ctx = SingleCallContext()
                    # start locked for the current thread, so the following
                    # gap won't let other threads populate the result
                    ctx.rlock.acquire()

            with ctx.rlock:
                if ctx.start_call:
                    ctx.start_call = False
                    ctx.rlock.release()  # unlock the starting lock
                    try:
                        result = method(self, *args, **kwargs)
                    except BaseException as e:
                        ctx.error = e
                        raise
                    finally:
                        # call is done, cleanup its entry
                        with lck:
                            del concurrent_calls[k]
                    ctx.result = result
                    return result

                else:
                    # call is done
                    if ctx.error:
                        raise ctx.error
                    # https://github.com/python/mypy/issues/3737
                    return cast(_RT, ctx.result)

        return wrapper

    if _method is None:
        return decorator
    else:
        return decorator(_method)


def cachedmethod_threadsafe(
    cache: Callable[[Any], MutableMapping[Any, _RT]],
    key: Callable[..., Any] = cachetools.keys.methodkey,
    lock: Callable[[Any], _LockType] | None = None,
) -> Callable[..., Callable[..., _RT]]:
    """Threadsafe variant of cachetools.cachedmethod."""
    lock = _ensure_lock(lock)

    def decorator(method: Callable[..., _RT]) -> Callable[..., _RT]:
        @cachetools.cachedmethod(cache=cache, key=key, lock=lock)
        @single_call_method(key=key, lock=lock)
        @functools.wraps(method)
        def wrapper(self: Any, *args: tuple, **kwargs: dict) -> _RT:
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


# AUTH MODULE CONFIGURATION OPTIONS
@dataclasses.dataclass(frozen=True, kw_only=True)
class CacheConfig:
    """Cache configuration."""

    # max number of entries in the token -> user LRU cache
    token_max_size: int
    # max number of authenticated org/repos TTL(LRU) for each user
    auth_max_size: int
    # age of user's org/repo authorizations able to WRITE [seconds]
    auth_write_ttl: float
    # age of user's org/repo authorizations NOT able to WRITE [seconds]
    auth_other_ttl: float

    class Schema(ma.Schema):
        token_max_size = ma.fields.Int(
            load_default=32, validate=ma.validate.Range(min=0)
        )
        auth_max_size = ma.fields.Int(
            load_default=32, validate=ma.validate.Range(min=0)
        )
        auth_write_ttl = ma.fields.Float(
            load_default=15 * 60.0, validate=ma.validate.Range(min=0)
        )
        auth_other_ttl = ma.fields.Float(
            load_default=30.0, validate=ma.validate.Range(min=0)
        )

        @ma.post_load
        def make_object(
            self, data: Mapping[str, Any], **_kwargs: Mapping
        ) -> "CacheConfig":
            return CacheConfig(**data)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Config:
    """General configuration.
    Create this class using from_dict() method that applies schema validation
    and proper default values.
    """

    # base URL for the GitHub API
    # (enterprise server has API at <hostname>/api/v3/)
    api_url: str
    # GitHub API version to target (set to None for the default latest)
    api_version: str | None
    # cache config above
    cache: CacheConfig

    class Schema(ma.Schema):
        api_url = ma.fields.Url(load_default="https://api.github.com")
        api_version = ma.fields.String(
            load_default="2022-11-28", allow_none=True
        )
        # always provide default CacheConfig when not present in the input
        cache = ma.fields.Nested(
            CacheConfig.Schema(),
            load_default=lambda: CacheConfig.Schema().load({}),
        )

        @ma.post_load
        def make_object(
            self, data: MutableMapping[str, Any], **_kwargs: Mapping
        ) -> "Config":
            data["api_url"] = data["api_url"].rstrip("/")
            return Config(**data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Config":
        return cast(Config, cls.Schema().load(data, unknown=ma.RAISE))


# CORE AUTH
@dataclasses.dataclass(frozen=True, slots=True)
class _CoreGithubIdentity:
    """Entries uniquely identifying a GitHub user (from a token).

    This serves as a key to mappings/caches of unique users.
    """

    id: str
    github_id: str

    @classmethod
    def from_token(
        cls, token_data: Mapping[str, Any]
    ) -> "_CoreGithubIdentity":
        return cls(*itemgetter("login", "id")(token_data))


class GithubIdentity(Identity):
    """User identity belonging to an authentication token.

    Tracks user's permission for particular organizations/repositories.
    """

    def __init__(
        self,
        core_identity: _CoreGithubIdentity,
        token_data: Mapping[str, Any],
        cc: CacheConfig,
    ) -> None:
        super().__init__(
            token_data.get("name"), core_identity.id, token_data.get("email")
        )
        self.core_identity = core_identity

        # Expiring cache of authorized repos with different TTL for each
        # permission type. It's assumed that anyone granted the WRITE
        # permission will likely keep it longer than those who can only READ
        # or have no permissions whatsoever. Caching the latter has the
        # complementing effect of keeping unauthorized entities from hammering
        # the GitHub API.
        def expiration(_key: Any, value: set[Permission], now: float) -> float:
            ttl = (
                cc.auth_write_ttl
                if Permission.WRITE in value
                else cc.auth_other_ttl
            )
            return now + ttl

        # size-unlimited proxy cache to ensure at least one successful hit
        self._auth_cache_read_proxy: MutableMapping[
            Any, set[Permission]
        ] = cachetools.TTLCache(math.inf, 60.0)
        self._auth_cache = cachetools.TLRUCache(cc.auth_max_size, expiration)
        self._auth_cache_lock = Lock()

    def __getattr__(self, attr: str) -> Any:
        # proxy to the core_identity for its attributes
        return getattr(self.core_identity, attr)

    def permissions(
        self, org: str, repo: str, *, authoritative: bool = False
    ) -> set[Permission] | None:
        """Return user's permission set for an org/repo."""
        key = cachetools.keys.hashkey(org, repo)
        with self._auth_cache_lock:
            # first check if the permissions are in the proxy cache
            if authoritative:
                # pop the entry from the proxy cache to be stored properly
                permission = self._auth_cache_read_proxy.pop(key, None)
            else:
                # just get it when only peeking
                permission = self._auth_cache_read_proxy.get(key)
            # if not found in the proxy, check the regular auth cache
            if permission is None:
                return self._auth_cache.get(key)
            # try moving proxy permissions to the regular cache
            if authoritative:
                with suppress(ValueError):
                    self._auth_cache[key] = permission
            return permission

    def authorize(
        self, org: str, repo: str, permissions: set[Permission] | None
    ) -> None:
        """Save user's permission set for an org/repo."""
        key = cachetools.keys.hashkey(org, repo)
        # put the discovered permissions into the proxy cache
        # to ensure at least one successful 'authoritative' read
        with self._auth_cache_lock:
            self._auth_cache_read_proxy[key] = (
                permissions if permissions is not None else set()
            )

    def is_authorized(
        self,
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> bool:
        permissions = self.permissions(organization, repo, authoritative=True)
        return permission in permissions if permissions else False

    def cache_ttl(self, permissions: set[Permission]) -> float:
        """Return default cache TTL [seconds] for a certain permission set."""
        return self._auth_cache.ttu(None, permissions, 0.0)


class GithubAuthenticator:
    """Main class performing GitHub "proxy" authentication/authorization."""

    @dataclasses.dataclass
    class CallContext:
        """Helper class to pass common auth request variables around."""

        # original flask request to be authenticated
        request: dataclasses.InitVar[flask.Request]
        # requests session to reuse a connection to GitHub
        session: requests.Session
        # fields inferred from request
        org: str = dataclasses.field(init=False)
        repo: str = dataclasses.field(init=False)
        token: str = dataclasses.field(init=False)

        def _extract_token(self, request: flask.Request) -> str:
            if request.authorization is None:
                raise Unauthorized("Authorization required")

            token = (
                request.authorization.password or request.authorization.token
            )
            if token is None:
                _logger.warning(
                    f"Request to {self.org}/{self.repo} has no auth token"
                )
                raise Unauthorized("Authorization token required")
            return token

        def __post_init__(self, request: flask.Request) -> None:
            org_repo_getter = itemgetter("organization", "repo")
            self.org, self.repo = org_repo_getter(request.view_args or {})
            self.token = self._extract_token(request)

    def __init__(self, cfg: Config) -> None:
        self._api_url = cfg.api_url
        self._api_headers = {"Accept": "application/vnd.github+json"}
        if cfg.api_version:
            self._api_headers["X-GitHub-Api-Version"] = cfg.api_version
        # user identities per token
        self._token_cache: MutableMapping[
            Any, GithubIdentity
        ] = cachetools.LRUCache(maxsize=cfg.cache.token_max_size)
        # unique user identities, to get the same identity that's
        # potentially already cached for a different token (same user)
        # If all the token entries for one user get evicted from the
        # token cache, the user entry here automatically ceases to exist too.
        self._cached_users: MutableMapping[
            Any, GithubIdentity
        ] = weakref.WeakValueDictionary()
        self._cache_lock = RLock()
        self._cache_config = cfg.cache

    def _api_get(self, uri: str, ctx: CallContext) -> Mapping[str, Any]:
        response = ctx.session.get(
            f"{self._api_url}{uri}",
            headers={"Authorization": f"Bearer {ctx.token}"},
        )
        response.raise_for_status()
        return cast(Mapping[str, Any], response.json())

    @cachedmethod_threadsafe(
        attrgetter("_token_cache"),
        lambda self, ctx: cachetools.keys.hashkey(ctx.token),
        attrgetter("_cache_lock"),
    )
    def _authenticate(self, ctx: CallContext) -> GithubIdentity:
        """Return internal GitHub user identity for a GitHub token in ctx."""
        _logger.debug("Authenticating user")
        try:
            token_data = self._api_get("/user", ctx)
        except requests.exceptions.RequestException as e:
            _logger.warning(msg := f"Couldn't authenticate the user: {e}")
            raise Unauthorized(msg) from None

        core_identity = _CoreGithubIdentity.from_token(token_data)
        # check if we haven't seen this identity before
        # guard the code with the same lock as the _token_cache
        with self._cache_lock:
            try:
                user = self._cached_users[core_identity]
            except KeyError:
                user = GithubIdentity(
                    core_identity, token_data, self._cache_config
                )
                self._cached_users[core_identity] = user
        return user

    @staticmethod
    def _perm_list(permissions: set[Permission]) -> str:
        return f"[{', '.join(sorted(p.value for p in permissions))}]"

    @single_call_method(
        key=lambda self, ctx, user: cachetools.keys.hashkey(
            ctx.org, ctx.repo, user.core_identity
        )
    )
    def _authorize(self, ctx: CallContext, user: GithubIdentity) -> None:
        org, repo = ctx.org, ctx.repo
        org_repo = f"{org}/{repo}"
        if (permissions := user.permissions(org, repo)) is not None:
            perm_list = self._perm_list(permissions)
            _logger.debug(
                f"{user.id} is already temporarily authorized for "
                f"{org_repo}: {perm_list}"
            )
        else:
            _logger.debug(f"Checking {user.id}'s permissions for {org_repo}")
            try:
                repo_data = self._api_get(
                    f"/repos/{org_repo}/collaborators/{user.id}/permission",
                    ctx,
                )
            except requests.exceptions.RequestException as e:
                msg = (
                    f"Failed to find {user.id}'s permissions for "
                    f"{org_repo}: {e}"
                )
                _logger.warning(msg)
                raise Unauthorized(msg) from None

            gh_permission = repo_data.get("permission")
            _logger.debug(
                f"User {user.id} has '{gh_permission}' GitHub permission "
                f"for {org_repo}"
            )
            permissions = set()
            if gh_permission in ("admin", "write"):
                permissions = Permission.all()
            elif gh_permission == "read":
                permissions = {Permission.READ, Permission.READ_META}
            perm_list = self._perm_list(permissions)
            ttl = user.cache_ttl(permissions)
            _logger.debug(
                f"Authorizing {user.id} (for {ttl}s) for "
                f"{org_repo}: {perm_list}"
            )
            user.authorize(org, repo, permissions)

    def __call__(self, request: flask.Request) -> Identity | None:
        _logger.debug(
            f"Handling auth request from pid: {os.getpid()}. "
            f"tid: {threading.get_native_id()}"
        )
        with requests.Session() as session:
            session.headers.update(self._api_headers)
            ctx = self.CallContext(request, session)
            user: GithubIdentity = self._authenticate(ctx)
            _logger.info(f"Authenticated the user as {user}")
            self._authorize(ctx, user)
            return user

    @property
    def api_url(self) -> str:
        return self._api_url


def factory(**options: Any) -> GithubAuthenticator:
    """Build GitHub Authenticator from supplied options."""
    config = Config.from_dict(options)
    return GithubAuthenticator(config)
