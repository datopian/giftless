"""Tests for the Google Cloud Storage storage backend."""
from pathlib import Path

import google.cloud.storage  # noqa: F401 (used implicitly by storage backend)
import pytest

from ..mocks.google_cloud_storage import MockGoogleCloudStorage
from . import ExternalStorageAbstractTests, StreamingStorageAbstractTests

MOCK_GCP_PROJECT_NAME = "giftless-tests"
MOCK_GCP_BUCKET_NAME = "giftless-tests-20240115"

# This is a valid but revoked key that we use in testing
MOCK_GCP_KEY_B64 = (
    "ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAiZ2lmdGxl"
    "c3MtdGVzdHMiLAogICJwcml2YXRlX2tleV9pZCI6ICI4MWRhNDcxNzhiYzhmYjE1MDU1NTg3"
    "OWRjZTczZThmZDlmOWI4NmJkIiwKICAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklW"
    "QVRFIEtFWS0tLS0tXG5NSUlFdkFJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLWXdnZ1Np"
    "QWdFQUFvSUJBUUNsYXdDOUEvZHBnbVJWXG5kYVg2UW5xY1N6YW5ueTdCVlgwVklwUHVjNzl2"
    "aFR2NWRwZXRaa29SQmV6Uzg2ZStHUHVyTmJIMU9rWEZrL2tkXG5SNHFqMDV6SXlYeWxiQUVx"
    "Sk1BV24zZFY0VUVRVFlmRitPY0ltZUxpcjR3cW9pTldDZDNJaHErNHVVeU1WRDMxXG5wc1Fl"
    "cWVxcWV6bVoyNG1oTjBLK2NQczNuSXlIK0lzZXFsWjJob3U3bUU3U2JsYXdjc04ramcyNmQ5"
    "YzFUZlpoXG42eFozVkpndGFtcUZvdlZmbEZwNFVvLy9tVGo0cXEwUWRUYk9SS1NEeVkxTWhk"
    "Q24veSsyaForVm9IUitFM0Z4XG5XRmc2VGFwRGJhc29heEp5YjRoZEFFK0JhbW14bklTL09G"
    "bElaMGVoL2tsRmlBTlJRMEpQb2dXRjFjVE9NcVFxXG4wMlVFV2V5ckFnTUJBQUVDZ2dFQUJN"
    "OE5odGVQNElhTEUxd2haclN0cEp5NWltMGgxenFXTVlCTU85WDR4KzJUXG5PZmRUYStLbWtp"
    "cUV1c1UyanNJdks1VUJPakVBcncxVU1RYnBaaEtoTDhub2c3dGkyNjVoMG1Ba1pzWlZOWHU0"
    "XG5UKzQ4REZ4YzQ4THlzaktXM1RCQVBSb2RRbkJLTVA3MnY4QThKMU5BYlMwZ3IvTW1TbEVi"
    "dm1tT2FuTU9ONXAwXG43djlscm9GMzFOakMzT05OY25pUlRYY01xT2tEbWt5LyszeVc2RldM"
    "MkJZV3RwcGN3L0s1TnYxdGNMTG5iajVhXG5Hc3dVMENtQXgyTEVoWEo0bndJaWlFR3h6UGZY"
    "VXNLcVhLL2JEZENKbDUzMTgraU9aSHNrdXR1OFlqQVpsdktpXG5yckNFUkFXZitLeTZ0WGhn"
    "KzJIRzJJbUc5cG8wRnUwTGlIU0ZVUURKY1FLQmdRRFQ5RDJEYm9SNWFGWW0wQlVSXG5vNGd4"
    "OHZGc0NyTEx0a09EZGx3U2wrT20yblFvY0JXSTEyTmF5QXRlL2xhVFZNRlorVks1bU9vYXl2"
    "WnljTU1YXG5SdXZJYmdCTFdHYkdwSXdXZnlDOGxRZEJYM09xZTZZSzZTMUU2VnNYUVN0aHQ0"
    "YUx3ZGpGQ2J6VU1lc1ZzREV5XG5FYU85aXlTUVlFTmFTN2V3amFzNUFVU1F0d0tCZ1FESHl4"
    "WUp3bWxpQzE4NEVyZ3lZSEFwYm9weXQzSVkzVGFKXG5yV2MrSGw5WDNzVEJzaFVQYy85Smhj"
    "anZKYWVzMlhrcEEwYmY5cis1MEcxUndua3dMWHZsbDJSU0FBNE05TG4rXG45cVlsNEFXNU9Q"
    "VTVJS0tKYVk1c0kzSHdXTXd6elRya3FBV3hNallJME9OSnBaWUVnSTVKN09sek1jYnhLREZx"
    "XG51MmpjYkFubnJRS0JnRlUxaklGSkxmTE5FazE2Tys0aWF6K0Jack5EdmN1TjA2aUhMYzYv"
    "eDJLdDBpTHJwSXlsXG40cWg5WWF6bjNSQlA4NGRqWjNGNzJ5bTRUTW1ITWJjcTZPRmo3N1Jh"
    "cnI3UEtnNWxQMWp4Sk1DUVNpVFFudGttXG5FdS93VEpHVnZvWURUUkRrZG13SVZTU05pTy9v"
    "TEc3dmpuOUY4QVltM1F6eEFjRDF3MDhnaGxzVEFvR0FidUthXG4vNTJqeVdPUVhGbWZXMjVF"
    "c2VvRTh2ZzNYZTlnZG5jRUJ1anFkNlZPeEVYbkJHV1h1U0dFVEo0MGVtMVVubHVRXG5PWHNF"
    "RzhlKzlKS2ZtZ3FVYWU5bElWR2dlclpVaUZveUNuRlVHK0d0MEIvNXRaUWRGSTF6ampacVZ4"
    "Ry9idXFHXG5CanRjMi9XN1A4T2tDQ21sVHdncTVPRXFqZXVGeWJ2cnpmSTBhUjBDZ1lCdVlY"
    "Wm5MMm1xeVNma0FnaGswRVVmXG5XeElDb1FmRDdCQlJBV3lmL3VwRjQ2NlMvRmhONUVreG5v"
    "dkZ2RlZyQjU1SHVHRTh2Qk4vTEZNVXlPU0xXQ0lIXG5RUG9ZcytNM0NLdGJWTXMxY1h2Tm5t"
    "ZFRhMnRyYjQ0SlQ5ZlFLbkVwa2VsbUdPdXJMNEVMdmFyUEFyR0x4VllTXG5jWFo1a1FBUy9G"
    "eGhFSDZSbnFSalFnPT1cbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS1cbiIsCiAgImNsaWVu"
    "dF9lbWFpbCI6ICJzb21lLXNlcnZpY2UtYWNjb3VudEBnaWZ0bGVzcy10ZXN0cy5pYW0uZ3Nl"
    "cnZpY2VhY2NvdW50LmNvbSIsCiAgImNsaWVudF9pZCI6ICIxMDk4NTYwMjgzNDI5MDI4ODI3"
    "MTUiLAogICJhdXRoX3VyaSI6ICJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0"
    "aDIvYXV0aCIsCiAgInRva2VuX3VyaSI6ICJodHRwczovL29hdXRoMi5nb29nbGVhcGlzLmNv"
    "bS90b2tlbiIsCiAgImF1dGhfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3"
    "dy5nb29nbGVhcGlzLmNvbS9vYXV0aDIvdjEvY2VydHMiLAogICJjbGllbnRfeDUwOV9jZXJ0"
    "X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9yb2JvdC92MS9tZXRhZGF0YS94"
    "NTA5L3NvbWUtc2VydmljZS1hY2NvdW50JTQwZ2lmdGxlc3MtdGVzdHMuaWFtLmdzZXJ2aWNl"
    "YWNjb3VudC5jb20iCn0K"
)


@pytest.fixture
def storage_backend(
    storage_path: Path,
) -> MockGoogleCloudStorage:
    """Provide a mock Google Cloud Storage backend for all GCS tests."""
    return MockGoogleCloudStorage(
        project_name=MOCK_GCP_PROJECT_NAME,
        bucket_name=MOCK_GCP_BUCKET_NAME,
        account_key_base64=MOCK_GCP_KEY_B64,
        path=storage_path,
    )


class TestGoogleCloudStorageBackend(
    StreamingStorageAbstractTests, ExternalStorageAbstractTests
):
    pass
