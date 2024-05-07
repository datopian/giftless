"""Test basic_external transfer adapter functionality."""
from typing import Any
from urllib.parse import urlencode

import flask
import pytest

from giftless.storage import ExternalStorage
from giftless.storage.exc import ObjectNotFoundError
from giftless.transfer import basic_external
from tests.helpers import expected_uri_prefix, legacy_endpoints_id


def test_factory_returns_object() -> None:
    """Test that the basic_external factory returns the right object(s)."""
    base_url = "https://s4.example.com/"
    lifetime = 300
    adapter = basic_external.factory(
        f"{__name__}:MockExternalStorageBackend",
        {"base_url": base_url},
        lifetime,
    )
    assert isinstance(
        adapter, basic_external.BasicExternalBackendTransferAdapter
    )
    assert getattr(adapter.storage, "base_url", None) == base_url
    assert adapter.action_lifetime == lifetime


@pytest.mark.usefixtures("app_context")
@pytest.mark.parametrize(
    "app", [False, True], ids=legacy_endpoints_id, indirect=True
)
def test_upload_action_new_file(app: flask.Flask) -> None:
    adapter = basic_external.factory(
        f"{__name__}:MockExternalStorageBackend",
        {},
        900,
    )
    response = adapter.upload("myorg", "myrepo", "abcdef123456", 1234)
    exp_uri_prefix = expected_uri_prefix(app, "myorg", "myrepo")

    assert response == {
        "oid": "abcdef123456",
        "size": 1234,
        "authenticated": False,
        "actions": {
            "upload": {
                "href": "https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900",
                "header": {"x-foo-bar": "bazbaz"},
                "expires_in": 900,
            },
            "verify": {
                "href": f"http://giftless.local/{exp_uri_prefix}/objects/storage/verify",
                "header": {},
                "expires_in": 43200,
            },
        },
    }


@pytest.mark.usefixtures("app_context")
@pytest.mark.parametrize(
    "app", [False, True], ids=legacy_endpoints_id, indirect=True
)
def test_upload_action_extras_are_passed(app: flask.Flask) -> None:
    adapter = basic_external.factory(
        f"{__name__}:MockExternalStorageBackend", {}, 900
    )
    response = adapter.upload(
        "myorg", "myrepo", "abcdef123456", 1234, {"filename": "foo.csv"}
    )
    exp_uri_prefix = expected_uri_prefix(app, "myorg", "myrepo")

    assert response == {
        "oid": "abcdef123456",
        "size": 1234,
        "authenticated": False,
        "actions": {
            "upload": {
                "href": "https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900&filename=foo.csv",
                "header": {"x-foo-bar": "bazbaz"},
                "expires_in": 900,
            },
            "verify": {
                "href": f"http://giftless.local/{exp_uri_prefix}/objects/storage/verify",
                "header": {},
                "expires_in": 43200,
            },
        },
    }


@pytest.mark.usefixtures("app_context")
def test_upload_action_existing_file() -> None:
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[("myorg/myrepo", "abcdef123456")] = 1234

    response = adapter.upload("myorg", "myrepo", "abcdef123456", 1234)

    # We expect a response with no actions
    assert response == {
        "oid": "abcdef123456",
        "size": 1234,
    }


@pytest.mark.usefixtures("app_context")
def test_download_action_existing_file() -> None:
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[("myorg/myrepo", "abcdef123456")] = 1234
    response = adapter.download("myorg", "myrepo", "abcdef123456", 1234)

    assert response == {
        "oid": "abcdef123456",
        "size": 1234,
        "authenticated": False,
        "actions": {
            "download": {
                "href": "https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900",
                "header": {},
                "expires_in": 900,
            }
        },
    }


@pytest.mark.usefixtures("app_context")
def test_download_action_non_existing_file() -> None:
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[("myorg/myrepo", "123456abcdef")] = 1234
    response = adapter.download("myorg", "myrepo", "abcdef123456", 1234)

    assert response == {
        "oid": "abcdef123456",
        "size": 1234,
        "error": {"code": 404, "message": "Object does not exist"},
    }


@pytest.mark.usefixtures("app_context")
def test_download_action_size_mismatch() -> None:
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[("myorg/myrepo", "abcdef123456")] = 1234
    response = adapter.download("myorg", "myrepo", "abcdef123456", 12345)

    assert response == {
        "oid": "abcdef123456",
        "size": 12345,
        "error": {"code": 422, "message": "Object size does not match"},
    }


@pytest.mark.usefixtures("app_context")
def test_download_action_extras_are_passed() -> None:
    storage = MockExternalStorageBackend()
    adapter = basic_external.BasicExternalBackendTransferAdapter(storage, 900)

    # Add an "existing object"
    storage.existing_objects[("myorg/myrepo", "abcdef123456")] = 1234
    response = adapter.download(
        "myorg", "myrepo", "abcdef123456", 1234, {"filename": "foo.csv"}
    )

    assert response == {
        "oid": "abcdef123456",
        "size": 1234,
        "authenticated": False,
        "actions": {
            "download": {
                "href": "https://cloudstorage.example.com/myorg/myrepo/abcdef123456?expires_in=900&filename=foo.csv",
                "header": {},
                "expires_in": 900,
            }
        },
    }


class MockExternalStorageBackend(ExternalStorage):
    """Implementation of mock adapter for the basic external transfer adapter.

    Typically, "external" backends are cloud providers - so this backend can
    be used in testing to test the transfer adapter's behavior without
    accessing an actual cloud provider.
    """

    def __init__(
        self, base_url: str = "https://cloudstorage.example.com/"
    ) -> None:
        self.existing_objects: dict[tuple[str, str], int] = {}
        self.base_url = base_url

    def exists(self, prefix: str, oid: str) -> bool:
        return (prefix, oid) in self.existing_objects

    def get_size(self, prefix: str, oid: str) -> int:
        try:
            return self.existing_objects[(prefix, oid)]
        except KeyError:
            raise ObjectNotFoundError("Object does not exist") from None

    def get_upload_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(
                        prefix, oid, expires_in, extra
                    ),
                    "header": {"x-foo-bar": "bazbaz"},
                    "expires_in": expires_in,
                }
            }
        }

    def get_download_action(
        self,
        prefix: str,
        oid: str,
        size: int,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(
                        prefix, oid, expires_in, extra
                    ),
                    "header": {},
                    "expires_in": 900,
                }
            }
        }

    def _get_signed_url(
        self,
        prefix: str,
        oid: str,
        expires_in: int,
        extra: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.base_url}{prefix}/{oid}?expires_in={expires_in}"
        if extra:
            url = f"{url}&{urlencode(extra, doseq=False)}"
        return url
