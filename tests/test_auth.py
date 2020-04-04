"""Unit tests for auth module
"""
import pytest

from giftless.auth import allow_anon
from giftless.auth.identity import DefaultIdentity, Permission


def test_default_identity_properties():
    """Test the basic properties of the default identity object
    """
    user = DefaultIdentity('arthur', 'kingofthebritons', 'arthur@camelot.gov.uk')
    assert user.name == 'arthur'
    assert user.id == 'kingofthebritons'
    assert user.email == 'arthur@camelot.gov.uk'


@pytest.mark.parametrize('requested', [
    ({"permission": Permission.READ, "organization": "myorg", "repo": "somerepo"}),
    ({"permission": Permission.READ, "organization": "otherorg", "repo": "somerepo"}),
    ({"permission": Permission.READ, "organization": "myorg", "repo": "somerepo", "oid": "foobar"}),
    ({"permission": Permission.WRITE, "organization": "myorg", "repo": "somerepo"}),
])
def test_default_identity_denied_by_default(requested):
    user = DefaultIdentity('arthur', 'kingofthebritons', 'arthur@camelot.gov.uk')
    assert user.is_authorized(**requested) is False


@pytest.mark.parametrize('requested, expected', [
    ({"permission": Permission.READ, "organization": "myorg", "repo": "somerepo"}, True),
    ({"permission": Permission.READ, "organization": "otherorg", "repo": "somerepo"}, False),
    ({"permission": Permission.READ, "organization": "myorg", "repo": "somerepo"}, True),
    ({"permission": Permission.READ, "organization": "myorg", "repo": "somerepo", "oid": "someobject"}, True),
    ({"permission": Permission.READ, "organization": "myorg", "repo": "otherrepo"}, False),
])
def test_default_identity_allow_specific_repo(requested, expected):
    user = DefaultIdentity('arthur', 'kingofthebritons', 'arthur@camelot.gov.uk')
    user.allow(organization='myorg', repo='somerepo', permissions=Permission.all())
    assert expected is user.is_authorized(**requested)


@pytest.mark.parametrize('requested, expected', [
    ({"permission": Permission.READ, "organization": "otherorg", "repo": "somerepo"}, False),
    ({"permission": Permission.READ, "organization": "myorg", "repo": "somerepo"}, True),
    ({"permission": Permission.READ_META, "organization": "myorg", "repo": "somerepo"}, True),
    ({"permission": Permission.WRITE, "organization": "myorg", "repo": "somerepo"}, False),
    ({"permission": Permission.READ, "organization": "myorg", "repo": "otherrepo"}, True),
    ({"permission": Permission.WRITE, "organization": "myorg", "repo": "otherrepo"}, False),
])
def test_default_identity_allow_specific_org_permissions(requested, expected):
    user = DefaultIdentity('arthur', 'kingofthebritons', 'arthur@camelot.gov.uk')
    user.allow(organization='myorg', permissions={Permission.READ_META, Permission.READ})
    assert expected is user.is_authorized(**requested)


@pytest.mark.parametrize('requested, expected', [
    ({"organization": "myorg", "repo": "myrepo", "permission": Permission.READ}, True),
    ({"organization": "otherorg", "repo": "otherrepo", "permission": Permission.READ}, True),
    ({"organization": "otherorg", "repo": "otherrepo", "permission": Permission.READ_META}, True),
    ({"organization": "myorg", "repo": "myrepo", "permission": Permission.WRITE}, False),
    ({"organization": "otherorg", "repo": "otherrepo", "permission": Permission.WRITE}, False),
])
def test_allow_anon_read_only(requested, expected):
    """Test that an anon user with read only permissions works as expected
    """
    user = allow_anon.read_only(None)
    assert expected is user.is_authorized(**requested)


@pytest.mark.parametrize('requested, expected', [
    ({"organization": "myorg", "repo": "myrepo", "permission": Permission.READ}, True),
    ({"organization": "otherorg", "repo": "otherrepo", "permission": Permission.READ}, True),
    ({"organization": "otherorg", "repo": "otherrepo", "permission": Permission.READ_META}, True),
    ({"organization": "myorg", "repo": "myrepo", "permission": Permission.WRITE}, True),
    ({"organization": "otherorg", "repo": "otherrepo", "permission": Permission.WRITE}, True),
])
def test_allow_anon_read_write(requested, expected):
    """Test that an anon user with read only permissions works as expected
    """
    user = allow_anon.read_write(None)
    assert expected is user.is_authorized(**requested)


def test_anon_user_interface():
    """Test that an anonymous user has the right interface
    """
    user = allow_anon.read_only(None)
    assert isinstance(user, allow_anon.AnonymousUser)
    assert user.name == 'anonymous'
