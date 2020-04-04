"""Dummy authentication module

Always returns an `AnonymousUser` identity object.

Depending on whether "read only" or "read write" authentication was used, the
user is going to have read-only or read-write permissions on all objects.

Only use this in production if you want your Giftless server to allow anonymous
access. Most likely, this is not what you want unless you are deploying in a
closed, 100% trusted network.

If for some reason you want to allow anonymous users as a fall back (e.g. you
want to allow read-only access to anyone), be sure to load this authenticator
last.
"""
from .identity import DefaultIdentity, Permission


class AnonymousUser(DefaultIdentity):
    """An anonymous user object
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.name is None:
            self.name = 'anonymous'


def read_only(_):
    """Dummy authenticator that gives read-only permissions to everyone
    """
    user = AnonymousUser()
    user.allow(permissions={Permission.READ, Permission.READ_META})
    return user


def read_write(_):
    """Dummy authenticator that gives full permissions to everyone
    """
    user = AnonymousUser()
    user.allow(permissions=Permission.all())
    return user
