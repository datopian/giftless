"""Dummy authentication module

Always return an `AnonymousUser` identity object.

Only use this in production if you want your Giftless server to allow anonymous
access. As current Giftless doesn't do authorization at all, enabling this
authenticator means your Giftless deployment will allow everyone to do anything
without requiring any credentials.

Most likely, this is not what you want unless you are deploying in a
closed, 100% trusted network.

If for some reason you want to allow anonymous users as a fall back (e.g. you
have implemented some kind of authorization checks in a transfer adapter), be
sure to load this authenticator last.
"""


class AnonymousUser:
    pass


def authenticate(_):
    """Dummy authenticator
    """
    return AnonymousUser
