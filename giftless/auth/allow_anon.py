"""Dummy authentication module.

Always returns an `AnonymousUser` identity object.

Depending on whether "read only" or "read write" authentication was
used, the user is going to have read-only or read-write permissions on
all objects.

Only use this in production if you want your Giftless server to allow
anonymous access. Most likely, this is not what you want unless you
are deploying in a closed, 100% trusted network, or your server is
behind a proxy that handles authentication for the services it
manages.

If for some reason you want to allow anonymous users as a fallback
(e.g. you want to allow read-only access to anyone), be sure to load
this authenticator last.
"""
from typing import Any

from .identity import DefaultIdentity, Permission


class AnonymousUser(DefaultIdentity):
    """An anonymous user object."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.name is None:
            self.name = "anonymous"


def read_only(_: Any) -> AnonymousUser:
    """Give read-only permissions to everyone via AnonymousUser."""
    user = AnonymousUser()
    user.allow(permissions={Permission.READ, Permission.READ_META})
    return user


def read_write(_: Any) -> AnonymousUser:
    """Give full permissions to everyone via AnonymousUser."""
    user = AnonymousUser()
    user.allow(permissions=Permission.all())
    return user
