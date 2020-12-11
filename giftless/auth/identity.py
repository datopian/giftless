from abc import ABC
from collections import defaultdict
from enum import Enum
from typing import Dict, Optional, Set


class Permission(Enum):
    """System wide permissions
    """
    READ = 'read'
    READ_META = 'read-meta'
    WRITE = 'write'

    @classmethod
    def all(cls) -> Set['Permission']:
        return set(cls)


PermissionTree = Dict[Optional[str], Dict[Optional[str], Dict[Optional[str], Set[Permission]]]]


class Identity(ABC):
    """Base user identity object

    The goal of user objects is to contain some information about the user, and also
    to allow checking if the user is authorized to perform some actions.
    """
    name: Optional[str] = None
    id: Optional[str] = None
    email: Optional[str] = None

    def is_authorized(self, organization: str, repo: str, permission: Permission, oid: Optional[str] = None) -> bool:
        """Tell if user is authorized to perform an operation on an object / repo
        """
        pass

    def __repr__(self):
        return '<{} id:{} name:{}>'.format(self.__class__.__name__, self.id, self.name)


class DefaultIdentity(Identity):

    def __init__(self, name: Optional[str] = None, id: Optional[str] = None,  email: Optional[str] = None):
        self.name = name
        self.id = id
        self.email = email
        self._allowed: PermissionTree = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    def allow(self, organization: Optional[str] = None, repo: Optional[str] = None,
              permissions: Optional[Set[Permission]] = None, oid: Optional[str] = None):
        if permissions is None:
            self._allowed[organization][repo][oid] = set()
        else:
            self._allowed[organization][repo][oid].update(permissions)

    def is_authorized(self, organization: str, repo: str, permission: Permission, oid: Optional[str] = None):
        if organization in self._allowed:
            if repo in self._allowed[organization]:
                if oid in self._allowed[organization][repo]:
                    return permission in self._allowed[organization][repo][oid]
                elif None in self._allowed[organization][repo]:
                    return permission in self._allowed[organization][repo][None]
            elif None in self._allowed[organization]:
                return permission in self._allowed[organization][None][None]
        elif None in self._allowed and None in self._allowed[None]:
            return permission in self._allowed[None][None][oid]

        return False
