"""Objects for GitHub "proxy" authentication."""
import abc
import dataclasses
import functools
import logging
import math
import os
import threading
import weakref
from collections.abc import (
    Callable,
    Generator,
    Iterable,
    Mapping,
    MutableMapping,
)
from contextlib import AbstractContextManager, ExitStack, suppress
from operator import attrgetter, itemgetter
from threading import Lock, RLock
from types import TracebackType
from typing import Any, ClassVar, Protocol, TypeVar, cast, overload
from urllib.parse import parse_qs, urlparse

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


# AUTH MODULE CONFIGURATION OPTIONS (and their validation)
class RequestsTimeout(ma.fields.Field):
    """Marshmallow Field validating a requests library timeout."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        pos_float = ma.fields.Float(validate=ma.validate.Range(min=0))
        self.possible_fields = (
            ma.fields.Tuple((pos_float, pos_float)),
            pos_float,
        )

    def _deserialize(
        self,
        value: Any,
        attr: str | None,
        data: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Any:  # float | tuple[float, float]
        errors = {}
        for field in self.possible_fields:
            try:
                return field.deserialize(value, **kwargs)
            except ma.ValidationError as error:  # noqa: PERF203
                if error.valid_data is not None:
                    # parsing partially successful, don't bother with the rest
                    raise
                errors.update({field.__class__.__name__: error.messages})
        raise ma.ValidationError(errors)


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
    # GitHub API requests timeout
    api_timeout: float | tuple[float, float]
    # Orgs and repos this instance is restricted to
    restrict_to: dict[str, list[str] | None] | None
    # cache config above
    cache: CacheConfig

    class Schema(ma.Schema):
        api_url = ma.fields.Url(load_default="https://api.github.com")
        api_version = ma.fields.String(
            load_default="2022-11-28", allow_none=True
        )
        api_timeout = RequestsTimeout(load_default=(5.0, 10.0))
        restrict_to = ma.fields.Dict(
            keys=ma.fields.String(),
            values=ma.fields.List(ma.fields.String(), allow_none=True),
            load_default=None,
            allow_none=True,
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
@dataclasses.dataclass
class CallContext:
    """Helper class for GithubAuthenticator to hold various state variables
    bound to a single __call__() execution.
    It's also a context manager holding an open requests client session.
    """

    # authenticator config
    cfg: Config
    # original flask request to be authenticated
    request: dataclasses.InitVar[flask.Request]
    # fields inferred from request
    org: str = dataclasses.field(init=False)
    repo: str = dataclasses.field(init=False)
    user: str | None = dataclasses.field(init=False)
    token: str = dataclasses.field(init=False)
    # GitHub api call variables
    _api_url: str = dataclasses.field(init=False)
    _api_headers: dict[str, str] = dataclasses.field(
        init=False,
        default_factory=lambda: {"Accept": "application/vnd.github+json"},
    )
    # requests session to reuse a connection to GitHub
    _session: requests.Session | None = dataclasses.field(
        init=False, default=None
    )
    _exit_stack: ExitStack = dataclasses.field(
        init=False, default_factory=ExitStack
    )

    def __post_init__(self, request: flask.Request) -> None:
        org_repo_getter = itemgetter("organization", "repo")
        self.org, self.repo = org_repo_getter(request.view_args or {})
        self.user, self.token = self._extract_auth(request)
        self._check_restricted_to()

        self._api_url = self.cfg.api_url
        self._api_headers["Authorization"] = f"Bearer {self.token}"
        if self.cfg.api_version:
            self._api_headers["X-GitHub-Api-Version"] = self.cfg.api_version

    def _check_restricted_to(self) -> None:
        restrict_to = self.cfg.restrict_to
        if restrict_to:
            try:
                rest_repos = restrict_to[self.org]
            except KeyError:
                raise Unauthorized(
                    f"Unauthorized GitHub organization '{self.org}'"
                ) from None
            if rest_repos and self.repo not in rest_repos:
                raise Unauthorized(
                    f"Unauthorized GitHub repository '{self.org}/{self.repo}'"
                )

    def __enter__(self) -> "CallContext":
        self._session = self._exit_stack.enter_context(requests.Session())
        self._session.headers.update(self._api_headers)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Any:
        self._session = None
        self._exit_stack.close()

    def _extract_auth(self, request: flask.Request) -> tuple[str | None, str]:
        if request.authorization is None:
            raise Unauthorized("Authorization required")

        user = request.authorization.get("username")
        token = request.authorization.password or request.authorization.token
        if token is None:
            _logger.warning(
                f"Request to {self.org}/{self.repo} has no auth token"
            )
            raise Unauthorized("Authorization token required")
        return user, token

    def api_get(self, uri: str) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError(
                "CallContext is a context manager maintaining a requests "
                "session. Call api_get() only within its entered context."
            )
        response = self._session.get(
            f"{self._api_url}{uri}",
            headers=self._api_headers,
            timeout=self.cfg.api_timeout,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def api_get_paginated(
        self, uri: str, *, per_page: int = 30, list_name: str | None = None
    ) -> Generator[dict[str, Any], None, None]:
        if self._session is None:
            raise RuntimeError(
                "CallContext is a context manager maintaining a requests "
                "session. Call api_get_paginated() only within its entered "
                "context."
            )

        per_page = min(max(per_page, 1), 100)
        list_name = list_name or uri.rsplit("/", 1)[-1]
        next_page = 1
        while next_page > 0:
            response = self._session.get(
                f"{self._api_url}{uri}",
                params={"per_page": per_page, "page": next_page},
                headers=self._api_headers,
                timeout=self.cfg.api_timeout,
            )
            response.raise_for_status()
            response_json: dict[str, Any] = response.json()

            yield from (item for item in response_json.get(list_name, []))

            # check the 'link' header for the 'next' page URL
            if next_url := response.links.get("next", {}).get("url"):
                # extract the page number from the URL that looks like
                # https://api.github.com/some/collections?page=4
                # urlparse(next_url).query returns "page=4"
                # parse_qs() parses that into {'page': ['4']}
                # when 'page' is missing, we supply a fake ['0'] to stop
                next_page = int(
                    parse_qs(urlparse(next_url).query).get("page", ["0"])[0]
                )
            else:
                next_page = 0

    @property
    def org_repo(self) -> str:
        return f"{self.org}/{self.repo}"


class GithubIdentity(Identity, abc.ABC):
    """GitHub identity belonging to an authentication token.

    Tracks identity's permission for particular organizations/repositories.
    """

    def __init__(
        self,
        id_: str | None,
        name: str | None = None,
        email: str | None = None,
        *,
        cc: CacheConfig,
    ) -> None:
        super().__init__(name, id_, email)

        # Expiring cache of authorized repos with different TTL for each
        # permission type. It's assumed that anyone granted the WRITE
        # permission will likely keep it longer than those who can only READ
        # or have no permissions whatsoever. Caching the latter has the
        # complementing effect of keeping unauthorized entities from hammering
        # the GitHub API.
        def _perm_ttl(perms: set[Permission]) -> float:
            if Permission.WRITE in perms:
                return cc.auth_write_ttl
            else:
                return cc.auth_other_ttl

        # expiration factory providing a 'ttu' function for 'TLRUCache'
        # respecting specified least_ttl
        def expiration(
            least_ttl: float | None = None,
        ) -> Callable[[Any, set[Permission], float], float]:
            if least_ttl is None or least_ttl <= 0.0:

                def _e(_key: Any, value: set[Permission], now: float) -> float:
                    return now + _perm_ttl(value)
            else:

                def _e(_key: Any, value: set[Permission], now: float) -> float:
                    return now + max(_perm_ttl(value), least_ttl)

            return _e

        # size-unlimited proxy cache to ensure at least one successful hit
        # by is_authorized
        self._auth_cache_read_proxy: MutableMapping[
            Any, set[Permission]
        ] = cachetools.TLRUCache(math.inf, expiration(60.0))
        self._auth_cache = cachetools.TLRUCache(cc.auth_max_size, expiration())
        self._auth_cache_lock = Lock()

    def __eq__(self, other: object) -> bool:
        field_get = attrgetter("id", "name", "email")
        return isinstance(other, type(self)) and field_get(self) == field_get(
            other
        )

    @classmethod
    def authenticate(cls, ctx: CallContext) -> "GithubIdentity":
        """Create a GitHub identity from the input data, run basic checks."""
        raise NotImplementedError

    def _authorize(self, ctx: CallContext) -> None:
        """Resolve and set access permissions for the particular identity."""
        raise NotImplementedError

    @single_call_method(
        key=lambda self, ctx: cachetools.keys.hashkey(
            ctx.org, ctx.repo, id(self)
        )
    )
    def authorize(self, ctx: CallContext) -> None:
        if (permissions := self._permissions(ctx.org, ctx.repo)) is not None:
            perm_list = self._perm_list(permissions)
            _logger.debug(
                f"{self.id} is already temporarily authorized for "
                f"{ctx.org_repo}: {perm_list}"
            )
        else:
            self._authorize(ctx)

    def _set_permissions(
        self,
        org: str,
        repo: str | None,
        permissions: set[Permission] | None,
        casual: bool = False,
    ) -> None:
        """Save user's permission set for an org/repo."""
        key = cachetools.keys.hashkey(org, repo)
        perm_set = permissions if permissions is not None else set()
        with self._auth_cache_lock:
            if casual:
                # put the discovered permissions right into the main cache
                # without any guarantees it will be retrieved later
                with suppress(ValueError):
                    self._auth_cache[key] = perm_set
            else:
                # put the discovered permissions into the proxy cache
                # to ensure at least one successful 'authoritative' read
                self._auth_cache_read_proxy[key] = perm_set

    def _permissions(
        self, org: str, repo: str | None, *, authoritative: bool = False
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

    @staticmethod
    def _perm_list(permissions: set[Permission]) -> str:
        return f"[{', '.join(sorted(p.value for p in permissions))}]"

    def is_authorized(
        self,
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> bool:
        permissions = self._permissions(organization, repo, authoritative=True)
        return permission in permissions if permissions else False

    def cache_ttl(self, permissions: set[Permission]) -> float:
        """Return default cache TTL [seconds] for a certain permission set."""
        return self._auth_cache.ttu(None, permissions, 0.0)


class GithubUserIdentity(GithubIdentity):
    """User identity belonging to an authentication token.

    Tracks user's permission for particular organizations/repositories.
    """

    @dataclasses.dataclass(frozen=True, slots=True)
    class CoreIdentity:
        """Entries uniquely identifying a GitHub user (from a token).

        This serves as a key to mappings/caches of unique users.
        """

        id: str
        github_id: str

        @classmethod
        def from_user_data(
            cls, user_data: Mapping[str, Any]
        ) -> "GithubUserIdentity.CoreIdentity":
            return cls(*itemgetter("login", "id")(user_data))

    # unique user identities, to get the same identity that's
    # potentially already cached for a different token (same user)
    # If all the token entries for one user get evicted from the
    # token cache, the user entry here automatically ceases to exist too.
    _cached_users: ClassVar[
        MutableMapping["GithubUserIdentity.CoreIdentity", "GithubUserIdentity"]
    ] = weakref.WeakValueDictionary()
    _cache_lock: ClassVar[_LockType] = RLock()

    def __init__(
        self,
        core_identity: CoreIdentity,
        user_data: Mapping[str, Any],
        cc: CacheConfig,
    ) -> None:
        super().__init__(
            core_identity.id,
            user_data.get("name"),
            user_data.get("email"),
            cc=cc,
        )
        self.core_identity = core_identity

    def __getattr__(self, attr: str) -> Any:
        # proxy to the core_identity for its attributes
        return getattr(self.core_identity, attr)

    @classmethod
    def authenticate(cls, ctx: CallContext) -> "GithubIdentity":
        """Return internal GitHub user identity for a GitHub token in ctx."""
        _logger.debug("Authenticating user")
        try:
            user_data = ctx.api_get("/user")
        except requests.exceptions.RequestException as e:
            _logger.warning(msg := f"Couldn't authenticate the user: {e}")
            raise Unauthorized(msg) from None

        core_identity = cls.CoreIdentity.from_user_data(user_data)
        # check if we haven't seen this identity before
        with cls._cache_lock:
            try:
                user = cls._cached_users[core_identity]
            except KeyError:
                user = GithubUserIdentity(
                    core_identity, user_data, ctx.cfg.cache
                )
                cls._cached_users[core_identity] = user
        _logger.info(f"Authenticated the user as {user}")
        return user

    def _authorize(self, ctx: CallContext) -> None:
        org_repo = ctx.org_repo
        _logger.debug(f"Checking {self.id}'s permissions for {org_repo}")
        try:
            repo_data = ctx.api_get(
                f"/repos/{org_repo}/collaborators/{self.id}/permission",
            )
        except requests.exceptions.RequestException as e:
            msg = (
                f"Failed to find {self.id}'s permissions for "
                f"{org_repo}: {e}"
            )
            _logger.warning(msg)
            raise Unauthorized(msg) from None

        gh_permission = repo_data.get("permission")
        _logger.debug(
            f"User {self.id} has '{gh_permission}' GitHub permission "
            f"for {org_repo}"
        )
        permissions = set()
        if gh_permission in ("admin", "write"):
            permissions = Permission.all()
        elif gh_permission == "read":
            permissions = {Permission.READ, Permission.READ_META}
        perm_list = self._perm_list(permissions)
        ttl = self.cache_ttl(permissions)
        _logger.debug(
            f"Authorizing {self.id} (for {ttl}s) for "
            f"{org_repo}: {perm_list}"
        )
        self._set_permissions(ctx.org, ctx.repo, permissions)


class GithubAppIdentity(GithubIdentity):
    """App Installation identity belonging to an authentication token.

    Tracks app's permission for particular organization/repositories.
    GitHub App installation gets a particular set of permissions per one
    user/org and a potential list of repositories that this app is allowed
    to act upon.
    """

    def __init__(
        self, org: str, installation_data: dict[str, Any], *, cc: CacheConfig
    ) -> None:
        super().__init__(
            str(installation_data["id"]), installation_data["app_slug"], cc=cc
        )
        self.client_id: str = installation_data["client_id"]
        self.app_id = str(installation_data["app_id"])
        self._orig_org = org
        self._orig_installation_data: dict[str, Any] | None = installation_data

    def __eq__(self, other: object) -> bool:
        field_get = attrgetter("client_id", "app_id")
        return (
            isinstance(other, type(self))
            and super().__eq__(other)
            and field_get(self) == field_get(other)
        )

    @staticmethod
    def _get_installation(
        ctx: CallContext, id_: str | None = None
    ) -> dict[str, Any]:
        """Get the GitHub App installation per its id or the user
        from Basic auth.

        This is a GitHub App acting on its own behalf.
        Its id must come as the username in the Basic auth;
        unlike a user, an app "installation" can't be identified from a token.
        """
        some_id = id_ or ctx.user
        _logger.debug("Authenticating GitHub App")
        if not some_id:
            msg = (
                "Couldn't authenticate the GitHub App. Its Installation ID"
                ", App ID or Client ID must be sent as the username within"
                " the Authorization header's Basic auth payload."
            )
            _logger.warning(msg)
            raise Unauthorized(msg)

        # get the list of org's GitHub App installations
        org = ctx.org
        _logger.debug(
            f"Checking Github App installation {some_id} permissions for {org}"
        )
        try:
            org_installations = ctx.api_get(f"/orgs/{org}/installations")
        except requests.exceptions.RequestException as e:
            msg = (
                f"Failed to get a list of Github App installations for "
                f"{org}: {e}. Make sure the app has the 'Administration' "
                f"organization (read) permission."
            )
            _logger.warning(msg)
            raise Unauthorized(msg) from None

        # find the particular GitHub App id in the installations
        # if the id_ is missing, search among all possible ids
        if id_ is None:

            def pick_ids(inst: dict[str, Any]) -> Iterable[str]:
                return (
                    str(inst.get("id")),
                    cast(str, inst.get("client_id")),
                    str(inst.get("app_id")),
                    cast(str, inst.get("app_slug")),
                )
        # otherwise just aim for the installation id
        else:

            def pick_ids(inst: dict[str, Any]) -> Iterable[str]:
                return (str(inst.get("id")),)

        _logger.debug(
            f"Looking for Github App installation {some_id} details."
        )
        try:
            installation: dict[str, Any] = next(
                inst
                for inst in org_installations["installations"]
                if some_id in pick_ids(inst)
            )
        except StopIteration:
            msg = (
                f"Failed to find id {some_id} in the list of Github App "
                f"installations for {org}."
            )
            _logger.warning(msg)
            raise Unauthorized(msg) from None
        return installation

    @classmethod
    def authenticate(cls, ctx: CallContext) -> "GithubIdentity":
        gh_installation = cls._get_installation(ctx)
        identity = cls(ctx.org, gh_installation, cc=ctx.cfg.cache)
        _logger.info(
            f"Authenticated the GitHub App '{identity.name}' installation "
            f"{identity.id}."
        )
        return identity

    def _set_permissions_for_repositories(
        self, ctx: CallContext, permissions: set[Permission]
    ) -> None:
        _logger.debug(
            f"Getting Github App {self.name} installation {self.id} "
            f"repositories."
        )
        org, repo = ctx.org, ctx.repo
        # one (final result) less than the auth cache free space
        to_cache_casually = max(
            0.0, self._auth_cache.maxsize - self._auth_cache.currsize - 1
        )
        gh_repos = ctx.api_get_paginated("/installation/repositories")
        try:
            for i, r in enumerate(gh_repos):
                r_org = r["owner"]["login"]
                r_repo = r["name"]
                # is it the repo we're looking for?
                if r_org == org and r_repo == repo:
                    self._set_permissions(org, repo, permissions)
                    # we found it, stop casual caching
                    break
                if i < to_cache_casually:
                    # we're not looking for this repo, but
                    # while we're here, we might as well cache it
                    self._set_permissions(
                        r_org, r_repo, permissions, casual=True
                    )

        except requests.exceptions.RequestException as e:
            msg = (
                f"Failed to get Github App {self.name} installation {self.id} "
                f"repositories: {e}"
            )
            _logger.warning(msg)
            raise Unauthorized(msg) from None

    def _authorize(self, ctx: CallContext) -> None:
        org = ctx.org
        # reuse eventual GitHub App installation data from the authentication
        if self._orig_installation_data:
            if self._orig_org != org:
                raise RuntimeError(
                    f"Initial authorization org mismatch: "
                    f"{org} != {self._orig_org}"
                )
            gh_installation = self._orig_installation_data
            self._orig_installation_data = None
        # or get new in case the authorization expired
        else:
            gh_installation = self._get_installation(ctx, self.id)

        if not (gh_permissions := gh_installation.get("permissions")):
            msg = (
                f"GitHub App {self.name} installation {self.id} "
                f"has no permissions in {org}."
            )
            _logger.warning(msg)
            raise Unauthorized(msg)

        if not (contents_permission := gh_permissions.get("contents")):
            msg = (
                f"GitHub App {self.name} installation {self.id} "
                f"has no 'contents' permissions in {org}."
            )
            _logger.warning(msg)
            raise Unauthorized(msg)

        if contents_permission == "write":
            permissions = Permission.all()
        elif contents_permission == "read":
            permissions = {Permission.READ_META, Permission.READ}
        else:
            msg = (
                f"GitHub App {self.name} installation {self.id} has no useful "
                f"'contents' permissions in {org} ({contents_permission})."
            )
            _logger.warning(msg)
            raise Unauthorized(msg)

        if gh_installation["repository_selection"] == "all":
            # this app controls all repositories in the org
            # no need to check particular repos, set a generic org permission
            self._set_permissions(org, None, permissions)
        else:
            # there are selected repositories, we must process them
            self._set_permissions_for_repositories(ctx, permissions)

    def _permissions(
        self, org: str, repo: str | None, *, authoritative: bool = False
    ) -> set[Permission] | None:
        # when the app can access all org repos, don't check the per-repo cache
        org_permissions = super()._permissions(
            org, None, authoritative=authoritative
        )
        return org_permissions or super()._permissions(
            org, repo, authoritative=authoritative
        )


class GithubAuthenticator:
    """Main class performing GitHub "proxy" authentication/authorization."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        # github identities per token
        self._token_cache: MutableMapping[
            Any, GithubIdentity
        ] = cachetools.LRUCache(maxsize=cfg.cache.token_max_size)
        self._cache_lock = RLock()
        self._cache_config = cfg.cache

    @cachedmethod_threadsafe(
        attrgetter("_token_cache"),
        lambda self, ctx: cachetools.keys.hashkey(ctx.token),
        attrgetter("_cache_lock"),
    )
    def _authenticate(self, ctx: CallContext) -> GithubIdentity:
        if ctx.token.startswith("ghs_"):
            identity = GithubAppIdentity.authenticate(ctx)
        else:
            identity = GithubUserIdentity.authenticate(ctx)
        return identity

    def __call__(self, request: flask.Request) -> Identity | None:
        _logger.debug(
            f"Handling auth request from pid: {os.getpid()}. "
            f"tid: {threading.get_native_id()}"
        )
        with CallContext(self._cfg, request) as ctx:
            identity: GithubIdentity = self._authenticate(ctx)
            identity.authorize(ctx)
            return identity

    @property
    def api_url(self) -> str:
        return self._cfg.api_url


def factory(**options: Any) -> GithubAuthenticator:
    """Build GitHub Authenticator from supplied options."""
    config = Config.from_dict(options)
    return GithubAuthenticator(config)
