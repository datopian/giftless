from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import pytest

from giftless.storage.exc import ObjectNotFound
from giftless.transfer import basic_external


def test_factory_returns_object():
    """Test that the basic_external factory returns the right object(s)
    """
    base_url = "https://s4.example.com/"
    lifetime = 300
    adapter = basic_external.factory('{}:MockExternalStorageBackend'.format(__name__, ),
                                     {"base_url": base_url},
                                     lifetime)
    assert isinstance(adapter, basic_external.BasicExternalBackendTransferAdapter)
    assert getattr(adapter.storage, 'base_url', None) == base_url
    assert adapter.action_lifetime == lifetime


@pytest.mark.usefixtures('app_context')
def test_upload_action_new_file():
    adapter = basic_external.factory('{}:MockExternalStorageBackend'.format(__name__, ), {}, 900)
    response = adapter.upload('myorg', 'myrepo', 'abcdef123456', 1234)

    assert response == {
        "oid": 'abcdef123456',
        "size": 1234,
        "authenticated": True,
        "actions": {
            "upload": {
                "href": 'https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900',
                "header": {"x-foo-bar": "bazbaz"},
                "expires_in": 900
            },
            "verify": {
                "href": 'http://giftless.local/myorg/myrepo/objects/storage/verify',
                "header": {},
                "expires_in": 43200
            }
        }
    }


@pytest.mark.usefixtures('app_context')
def test_upload_action_extras_are_passed():
    adapter = basic_external.factory('{}:MockExternalStorageBackend'.format(__name__), {}, 900)
    response = adapter.upload('myorg', 'myrepo', 'abcdef123456', 1234, {"filename": "foo.csv"})

    assert response == {
        "oid": 'abcdef123456',
        "size": 1234,
        "authenticated": True,
        "actions": {
            "upload": {
                "href": 'https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900&filename=foo.csv',
                "header": {"x-foo-bar": "bazbaz"},
                "expires_in": 900
            },
            "verify": {
                "href": 'http://giftless.local/myorg/myrepo/objects/storage/verify',
                "header": {},
                "expires_in": 43200
            }
        }
    }


@pytest.mark.usefixtures('app_context')
def test_upload_action_existing_file():
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[('myorg/myrepo', 'abcdef123456')] = 1234

    response = adapter.upload('myorg', 'myrepo', 'abcdef123456', 1234)

    # We expect a response with no actions
    assert response == {
        "oid": 'abcdef123456',
        "size": 1234,
    }


@pytest.mark.usefixtures('app_context')
def test_download_action_existing_file():
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[('myorg/myrepo', 'abcdef123456')] = 1234
    response = adapter.download('myorg', 'myrepo', 'abcdef123456', 1234)

    assert response == {
        "oid": 'abcdef123456',
        "size": 1234,
        "authenticated": True,
        "actions": {
            "download": {
                "href": 'https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900',
                "header": {},
                "expires_in": 900
            }
        }
    }


@pytest.mark.usefixtures('app_context')
def test_download_action_non_existing_file():
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[('myorg/myrepo', '123456abcdef')] = 1234
    response = adapter.download('myorg', 'myrepo', 'abcdef123456', 1234)

    assert response == {
        "oid": 'abcdef123456',
        "size": 1234,
        "error": {
            "code": 404,
            "message": "Object does not exist"
        }
    }


@pytest.mark.usefixtures('app_context')
def test_download_action_size_mismatch():
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[('myorg/myrepo', 'abcdef123456')] = 1234
    response = adapter.download('myorg', 'myrepo', 'abcdef123456', 12345)

    assert response == {
        "oid": 'abcdef123456',
        "size": 12345,
        "error": {
            "code": 422,
            "message": "Object size does not match"
        }
    }


@pytest.mark.usefixtures('app_context')
def test_download_action_extras_are_passed():
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[('myorg/myrepo', 'abcdef123456')] = 1234
    response = adapter.download('myorg', 'myrepo', 'abcdef123456', 1234, {"filename": "foo.csv"})

    assert response == {
        "oid": 'abcdef123456',
        "size": 1234,
        "authenticated": True,
        "actions": {
            "download": {
                "href": 'https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900&filename=foo.csv',
                "header": {},
                "expires_in": 900
            }
        }
    }


class MockExternalStorageBackend(basic_external.ExternalStorage):
    """A mock adapter for the basic external transfer adapter

    Typically, "external" backends are cloud providers - so this backend can
    be used in testing to test the transfer adapter's behavior without
    accessing an actual cloud provider.
    """
    def __init__(self, base_url: str = 'https://cloudstorage.example.com/'):
        self.existing_objects: Dict[Tuple[str, str], int] = {}
        self.base_url = base_url

    def exists(self, prefix: str, oid: str) -> bool:
        return (prefix, oid) in self.existing_objects

    def get_size(self, prefix: str, oid: str) -> int:
        try:
            return self.existing_objects[(prefix, oid)]
        except KeyError:
            raise ObjectNotFound("Object does not exist")

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(prefix, oid, expires_in, extra),
                    "header": {"x-foo-bar": "bazbaz"},
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(prefix, oid, expires_in, extra),
                    "header": {},
                    "expires_in": 900
                }
            }
        }

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int, extra: Optional[Dict[str, Any]] = None):
        url = '{}{}/{}?expires_in={}'.format(self.base_url, prefix, oid, expires_in)
        if extra:
            url = f'{url}&{urlencode(extra, doseq=False)}'
        return url
