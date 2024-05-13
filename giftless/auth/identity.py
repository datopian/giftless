"""Objects to support Giftless's concept of users and permissions."""
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum


class Permission(Enum):
    """System wide permissions."""

    READ = "read"
    READ_META = "read-meta"
    WRITE = "write"

    @classmethod
    def all(cls) -> set["Permission"]:
        return set(cls)


PermissionTree = dict[
    str | None, dict[str | None, dict[str | None, set[Permission]]]
]


class Identity(ABC):
    """Base user identity object.

    The goal of user objects is to contain some information about the
    user, and also to allow checking if the user is authorized to
    perform some actions.
    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        email: str | None = None,
    ) -> None:
        self.name = name
        self.id = id
        self.email = email

    @abstractmethod
    def is_authorized(
        self,
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> bool:
        """Determine whether user is authorized to perform an operation
        on an object or repo.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id:{self.id} name:{self.name}>"


class DefaultIdentity(Identity):
    """Default instantiable user identity class."""

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        email: str | None = None,
    ) -> None:
        super().__init__(name, id, email)
        self._allowed: PermissionTree = defaultdict(
            lambda: defaultdict(lambda: defaultdict(set))
        )

    def allow(
        self,
        organization: str | None = None,
        repo: str | None = None,
        permissions: set[Permission] | None = None,
        oid: str | None = None,
    ) -> None:
        if permissions is None:
            self._allowed[organization][repo][oid] = set()
        else:
            self._allowed[organization][repo][oid].update(permissions)

    def is_authorized(
        self,
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> bool:
        if organization in self._allowed:
            if repo in self._allowed[organization]:
                if oid in self._allowed[organization][repo]:
                    return permission in self._allowed[organization][repo][oid]
                elif None in self._allowed[organization][repo]:
                    return (
                        permission in self._allowed[organization][repo][None]
                    )
            elif None in self._allowed[organization]:
                return permission in self._allowed[organization][None][None]
        elif None in self._allowed and None in self._allowed[None]:
            return permission in self._allowed[None][None][oid]

        return False
