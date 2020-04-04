from typing import Any, Dict, Tuple

from giftless.transfer import basic_external


class MockExternalStorageBackend(basic_external.ExternalStorage):
    """A mock adapter for the basic external transfer adapter

    Typically, "external" backends are cloud providers - so this backend can
    be used in testing to test the transfer adapter's behavior without
    accessing an actual cloud provider.
    """
    def __init__(self, base_url: str = 'https://cloudstorage.example.com/'):
        self.existing_objects: Dict[Tuple[str, str], int] = {}
        self.base_url = base_url

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int) -> Dict[str, Any]:
        if (prefix, oid) in self.existing_objects and self.existing_objects[(prefix, oid)] == size:
            # No upload required, we already have this object
            return {}

        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(prefix, oid, expires_in),
                    "header": {
                        "x-ms-blob-type": "BlockBlob",
                    },
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int) -> Dict[str, Any]:
        try:
            if self.existing_objects[(prefix, oid)] != size:
                return {"error": {
                    "code": 422,
                    "message": "Object size does not match"
                }}
        except KeyError:
            # Object does not exist, return 404
            return {"error": {
                "code": 404,
                "message": "Object does not exist"
            }}

        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(prefix, oid, expires_in),
                    "header": {},
                    "expires_in": 900
                }
            }
        }

    def _get_signed_url(self, prefix: str, oid: str, expires_in: int):
        return '{}{}/{}?expires_in={}'.format(self.base_url, prefix, oid, expires_in)


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
