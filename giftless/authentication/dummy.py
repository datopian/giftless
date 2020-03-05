"""Dummy authentication module

Always return an `AnonymousUser` identity object.

Only use this in production if you want your Giftless server to be fully open
and allow everyone to do everything. This is unlikely in production setups,
unless Giftless is deployed in some kind of closed, trusted network.
"""


class AnonymousUser:
    pass


def authenticate(_):
    """Dummy authenticator
    """
    return AnonymousUser
