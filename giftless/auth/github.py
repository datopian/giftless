"""Objects for GitHub "proxy" authentication."""
import dataclasses
import functools
import logging
import os
import threading
from collections.abc import Callable, Mapping, MutableMapping
from contextlib import AbstractContextManager
from operator import attrgetter, itemgetter
from threading import Condition, Lock, RLock
from typing import Any

import cachetools.keys
import flask
import marshmallow as ma
import marshmallow.validate
import requests

from giftless.auth import Identity, Unauthorized
from giftless.auth.identity import Permission

_logger = logging.getLogger(__name__)


# THREAD SAFE CACHING UTILS
@dataclasses.dataclass(kw_only=True)
class SingleCallContext:
    """Thread-safety context for the single_call_method decorator."""

    # condition variable blocking a call with particular arguments
    cond: Condition = dataclasses.field(default_factory=Condition)
    # None - call not started, False - call ongoing, True - call done
    # the three states are needed to cover any spurious (pthread-like) wake-ups
    call_status: bool | None = None
    result: Any = None
    error: BaseException | None = None


def _ensure_lock(
    existing_lock: Callable[[Any], AbstractContextManager] | None,
) -> Callable[[Any], AbstractContextManager]:
    if existing_lock is None:
        default_lock = RLock()
        return lambda _self: default_lock
    return existing_lock


def single_call_method(
    _method: Callable[[...], Any] | None = None,
    *,
    key: Callable = cachetools.keys.methodkey,
    lock: Callable[[Any], AbstractContextManager] | None = None,
) -> Callable[[...], Any]:
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
    Each concurrent call is then guarded by its own lock/conditional variable.
    """
    lock = _ensure_lock(lock)

    def decorator(method: Callable) -> Callable:
        # tracking concurrent calls per method arguments
        concurrent_calls = {}

        @functools.wraps(method)
        def wrapper(self: Any, *args: tuple, **kwargs: dict) -> Any:
            lck = lock(self)
            k = key(self, *args, **kwargs)
            with lck:
                try:
                    ctx = concurrent_calls[k]
                except KeyError:
                    concurrent_calls[k] = ctx = SingleCallContext()
                    # start locked for the current thread, so the following
                    # gap won't let other threads populate the result
                    ctx.cond.acquire()

            with ctx.cond:
                if ctx.call_status is None:
                    # populating the result
                    ctx.call_status = False
                    try:
                        result = method(self, *args, **kwargs)
                    except BaseException as e:
                        ctx.error = e
                        raise
                    finally:
                        # call is done, cleanup its entry and notify threads
                        with lck:
                            del concurrent_calls[k]
                        ctx.cond.release()  # unlock the starting lock
                        ctx.cond.notify_all()
                    ctx.result = result
                    ctx.call_status = True
                    return result

                else:
                    # waiting for the result to get populated
                    while True:
                        if ctx.error:
                            raise ctx.error
                        if ctx.call_status:
                            return ctx.result
                        ctx.cond.wait()

        return wrapper

    if _method is None:
        return decorator
    else:
        return decorator(_method)


def cachedmethod_threadsafe(
    cache: Callable[[Any], MutableMapping],
    key: Callable = cachetools.keys.methodkey,
    lock: Callable[[Any], AbstractContextManager] | None = None,
) -> Callable:
    """Threadsafe variant of cachetools.cachedmethod."""
    lock = _ensure_lock(lock)

    def decorator(method: Callable) -> Callable:
        @cachetools.cachedmethod(cache=cache, key=key, lock=lock)
        @single_call_method(key=key, lock=lock)
        @functools.wraps(method)
        def wrapper(self: Any, *args: tuple, **kwargs: dict) -> Any:
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


# AUTH MODULE CONFIGURATION OPTIONS
@dataclasses.dataclass(frozen=True, kw_only=True)
class CacheConfig:
    """Cache configuration."""

    # max number of entries in the unique user LRU cache
    user_max_size: int
    # max number of entries in the token -> user LRU cache
    token_max_size: int
    # max number of authenticated org/repos TTL(LRU) for each user
    auth_max_size: int
    # age of user's org/repo authorizations able to WRITE [seconds]
    auth_write_ttl: float
    # age of user's org/repo authorizations NOT able to WRITE [seconds]
    auth_other_ttl: float

    class Schema(ma.Schema):
        user_max_size = ma.fields.Int(
            load_default=32, validate=ma.validate.Range(min=0)
        )
        token_max_size = ma.fields.Int(
            load_default=32, validate=ma.validate.Range(min=0)
        )
        # the auth cache must have at least one valid slot
        auth_max_size = ma.fields.Int(
            load_default=32, validate=ma.validate.Range(min=1)
        )
        auth_write_ttl = ma.fields.Float(
            load_default=15 * 60.0, validate=ma.validate.Range(min=1.0)
        )
        auth_other_ttl = ma.fields.Float(
            load_default=30.0, validate=ma.validate.Range(min=1.0)
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
            self, data: Mapping[str, Any], **_kwargs: Mapping
        ) -> "Config":
            return Config(**data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Config":
        return cls.Schema().load(data, unknown=ma.RAISE)


# CORE AUTH
class GithubIdentity(Identity):
    """User identity belonging to an authentication token.
    Tracks user's permission for particular organizations/repositories.
    """

    def __init__(
        self, login: str, id_: str, name: str, email: str, *, cc: CacheConfig
    ) -> None:
        super().__init__()
        self.login = login
        self.id = id_
        self.name = name
        self.email = email

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

        self._auth_cache = cachetools.TLRUCache(cc.auth_max_size, expiration)
        self._auth_cache_lock = Lock()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}"
            f"login:{self.login} id:{self.id} name:{self.name}>"
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and (self.login, self.id) == (
            other.login,
            other.id,
        )

    def __hash__(self) -> int:
        return hash((self.login, self.id))

    def permissions(self, org: str, repo: str) -> set[Permission] | None:
        key = cachetools.keys.hashkey(org, repo)
        with self._auth_cache_lock:
            return self._auth_cache.get(key)

    def authorize(
        self, org: str, repo: str, permissions: set[Permission] | None
    ) -> None:
        key = cachetools.keys.hashkey(org, repo)
        with self._auth_cache_lock:
            self._auth_cache[key] = (
                permissions if permissions is not None else set()
            )

    def is_authorized(
        self,
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> bool:
        permissions = self.permissions(organization, repo)
        return permissions and permission in permissions

    def cache_ttl(self, permissions: set[Permission]) -> float:
        """Return default cache TTL [seconds] for a certain permission set."""
        return self._auth_cache.ttu(None, permissions, 0.0)

    @staticmethod
    def cache_key(data: dict) -> tuple:
        """Return caching key from significant fields."""
        return cachetools.keys.hashkey(*itemgetter("login", "id")(data))

    @classmethod
    def from_dict(cls, data: dict, cc: CacheConfig) -> "GithubIdentity":
        return cls(*itemgetter("login", "id", "name", "email")(data), cc=cc)


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
            self.org, self.repo = request.path.split("/", maxsplit=3)[1:3]
            self.token = self._extract_token(request)

    def __init__(self, cfg: Config) -> None:
        self._api_url = cfg.api_url.rstrip("/")
        self._api_headers = {"Accept": "application/vnd.github+json"}
        if cfg.api_version:
            self._api_headers["X-GitHub-Api-Version"] = cfg.api_version
        # user identities per raw user data (keeping them authorized)
        self._user_cache = cachetools.LRUCache(maxsize=cfg.cache.user_max_size)
        # user identities per token (shortcut to the cached entries above)
        self._token_cache = cachetools.LRUCache(
            maxsize=cfg.cache.token_max_size
        )
        self._cache_config = cfg.cache

    def _api_get(self, uri: str, ctx: CallContext) -> dict:
        response = ctx.session.get(
            f"{self._api_url}{uri}",
            headers={"Authorization": f"Bearer {ctx.token}"},
        )
        response.raise_for_status()
        return response.json()

    @cachedmethod_threadsafe(
        attrgetter("_user_cache"),
        lambda self, data: GithubIdentity.cache_key(data),
    )
    def _get_user_cached(self, data: dict) -> GithubIdentity:
        """Return internal GitHub user identity from raw GitHub user data
        [cached per login & id].
        """
        return GithubIdentity.from_dict(data, self._cache_config)

    @cachedmethod_threadsafe(
        attrgetter("_token_cache"),
        lambda self, ctx: cachetools.keys.hashkey(ctx.token),
    )
    def _authenticate(self, ctx: CallContext) -> GithubIdentity:
        """Return internal GitHub user identity for a GitHub token in ctx
        [cached per token].
        """
        _logger.debug("Authenticating user")
        try:
            user_data = self._api_get("/user", ctx)
        except requests.exceptions.RequestException as e:
            _logger.warning(msg := f"Couldn't authenticate the user: {e}")
            raise Unauthorized(msg) from None

        # different tokens can bear the same identity
        return self._get_user_cached(user_data)

    @staticmethod
    def _perm_list(permissions: set[Permission]) -> str:
        return f"[{', '.join(sorted(p.value for p in permissions))}]"

    @single_call_method(
        key=lambda self, ctx, user: cachetools.keys.hashkey(
            ctx.org, ctx.repo, user
        )
    )
    def _authorize(self, ctx: CallContext, user: GithubIdentity) -> None:
        org, repo = ctx.org, ctx.repo
        org_repo = f"{org}/{repo}"
        if (permissions := user.permissions(org, repo)) is not None:
            perm_list = self._perm_list(permissions)
            _logger.debug(
                f"{user.login} is already temporarily authorized for "
                f"{org_repo}: {perm_list}"
            )
        else:
            _logger.debug(
                f"Checking {user.login}'s permissions for {org_repo}"
            )
            try:
                repo_data = self._api_get(
                    f"/repos/{org_repo}/collaborators/{user.login}/permission",
                    ctx,
                )
            except requests.exceptions.RequestException as e:
                msg = (
                    f"Failed to find {user.login}'s permissions for "
                    f"{org_repo}: {e}"
                )
                _logger.warning(msg)
                raise Unauthorized(msg) from None

            gh_permission = repo_data.get("permission")
            _logger.debug(
                f"User {user.login} has '{gh_permission}' GitHub permission "
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
                f"Authorizing {user.login} (for {ttl}s) for "
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
            user = self._authenticate(ctx)
            _logger.info(f"Authenticated the user as {user}")
            self._authorize(ctx, user)
            return user


def factory(**options: Mapping[str, Any]) -> GithubAuthenticator:
    """Build GitHub Authenticator from supplied options."""
    config = Config.from_dict(options)
    return GithubAuthenticator(config)
