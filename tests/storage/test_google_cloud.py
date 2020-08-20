"""Tests for the Google Cloud Storage storage backend
"""
import os
from typing import Generator

import pytest
from google.api_core.exceptions import GoogleAPIError  # type: ignore

from giftless.storage.google_cloud import GoogleCloudStorage

from . import ExternalStorageAbstractTests, StreamingStorageAbstractTests

MOCK_GCP_PROJECT_NAME = 'giftless-tests'
MOCK_GCP_BUCKET_NAME = 'giftless-tests-20200818'

# This is a valid but revoked key that we use in testing
MOCK_GCP_KEY_B64 = ("ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAiZ2lmdGxlc3MtdGVz"
                    "dHMiLAogICJwcml2YXRlX2tleV9pZCI6ICI4MWRhNDcxNzhiYzhmYjE1MDU1NTg3OWRjZTczZThmZDlm"
                    "OWI4NmJkIiwKICAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlF"
                    "dkFJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLWXdnZ1NpQWdFQUFvSUJBUUNsYXdDOUEvZHBnbVJW"
                    "XG5kYVg2UW5xY1N6YW5ueTdCVlgwVklwUHVjNzl2aFR2NWRwZXRaa29SQmV6Uzg2ZStHUHVyTmJIMU9r"
                    "WEZrL2tkXG5SNHFqMDV6SXlYeWxiQUVxSk1BV24zZFY0VUVRVFlmRitPY0ltZUxpcjR3cW9pTldDZDNJ"
                    "aHErNHVVeU1WRDMxXG5wc1FlcWVxcWV6bVoyNG1oTjBLK2NQczNuSXlIK0lzZXFsWjJob3U3bUU3U2Js"
                    "YXdjc04ramcyNmQ5YzFUZlpoXG42eFozVkpndGFtcUZvdlZmbEZwNFVvLy9tVGo0cXEwUWRUYk9SS1NE"
                    "eVkxTWhkQ24veSsyaForVm9IUitFM0Z4XG5XRmc2VGFwRGJhc29heEp5YjRoZEFFK0JhbW14bklTL09G"
                    "bElaMGVoL2tsRmlBTlJRMEpQb2dXRjFjVE9NcVFxXG4wMlVFV2V5ckFnTUJBQUVDZ2dFQUJNOE5odGVQ"
                    "NElhTEUxd2haclN0cEp5NWltMGgxenFXTVlCTU85WDR4KzJUXG5PZmRUYStLbWtpcUV1c1UyanNJdks1"
                    "VUJPakVBcncxVU1RYnBaaEtoTDhub2c3dGkyNjVoMG1Ba1pzWlZOWHU0XG5UKzQ4REZ4YzQ4THlzaktX"
                    "M1RCQVBSb2RRbkJLTVA3MnY4QThKMU5BYlMwZ3IvTW1TbEVidm1tT2FuTU9ONXAwXG43djlscm9GMzFO"
                    "akMzT05OY25pUlRYY01xT2tEbWt5LyszeVc2RldMMkJZV3RwcGN3L0s1TnYxdGNMTG5iajVhXG5Hc3dV"
                    "MENtQXgyTEVoWEo0bndJaWlFR3h6UGZYVXNLcVhLL2JEZENKbDUzMTgraU9aSHNrdXR1OFlqQVpsdktp"
                    "XG5yckNFUkFXZitLeTZ0WGhnKzJIRzJJbUc5cG8wRnUwTGlIU0ZVUURKY1FLQmdRRFQ5RDJEYm9SNWFG"
                    "WW0wQlVSXG5vNGd4OHZGc0NyTEx0a09EZGx3U2wrT20yblFvY0JXSTEyTmF5QXRlL2xhVFZNRlorVks1"
                    "bU9vYXl2WnljTU1YXG5SdXZJYmdCTFdHYkdwSXdXZnlDOGxRZEJYM09xZTZZSzZTMUU2VnNYUVN0aHQ0"
                    "YUx3ZGpGQ2J6VU1lc1ZzREV5XG5FYU85aXlTUVlFTmFTN2V3amFzNUFVU1F0d0tCZ1FESHl4WUp3bWxp"
                    "QzE4NEVyZ3lZSEFwYm9weXQzSVkzVGFKXG5yV2MrSGw5WDNzVEJzaFVQYy85SmhjanZKYWVzMlhrcEEw"
                    "YmY5cis1MEcxUndua3dMWHZsbDJSU0FBNE05TG4rXG45cVlsNEFXNU9QVTVJS0tKYVk1c0kzSHdXTXd6"
                    "elRya3FBV3hNallJME9OSnBaWUVnSTVKN09sek1jYnhLREZxXG51MmpjYkFubnJRS0JnRlUxaklGSkxm"
                    "TE5FazE2Tys0aWF6K0Jack5EdmN1TjA2aUhMYzYveDJLdDBpTHJwSXlsXG40cWg5WWF6bjNSQlA4NGRq"
                    "WjNGNzJ5bTRUTW1ITWJjcTZPRmo3N1JhcnI3UEtnNWxQMWp4Sk1DUVNpVFFudGttXG5FdS93VEpHVnZv"
                    "WURUUkRrZG13SVZTU05pTy9vTEc3dmpuOUY4QVltM1F6eEFjRDF3MDhnaGxzVEFvR0FidUthXG4vNTJq"
                    "eVdPUVhGbWZXMjVFc2VvRTh2ZzNYZTlnZG5jRUJ1anFkNlZPeEVYbkJHV1h1U0dFVEo0MGVtMVVubHVR"
                    "XG5PWHNFRzhlKzlKS2ZtZ3FVYWU5bElWR2dlclpVaUZveUNuRlVHK0d0MEIvNXRaUWRGSTF6ampacVZ4"
                    "Ry9idXFHXG5CanRjMi9XN1A4T2tDQ21sVHdncTVPRXFqZXVGeWJ2cnpmSTBhUjBDZ1lCdVlYWm5MMm1x"
                    "eVNma0FnaGswRVVmXG5XeElDb1FmRDdCQlJBV3lmL3VwRjQ2NlMvRmhONUVreG5vdkZ2RlZyQjU1SHVH"
                    "RTh2Qk4vTEZNVXlPU0xXQ0lIXG5RUG9ZcytNM0NLdGJWTXMxY1h2Tm5tZFRhMnRyYjQ0SlQ5ZlFLbkVw"
                    "a2VsbUdPdXJMNEVMdmFyUEFyR0x4VllTXG5jWFo1a1FBUy9GeGhFSDZSbnFSalFnPT1cbi0tLS0tRU5E"
                    "IFBSSVZBVEUgS0VZLS0tLS1cbiIsCiAgImNsaWVudF9lbWFpbCI6ICJzb21lLXNlcnZpY2UtYWNjb3Vu"
                    "dEBnaWZ0bGVzcy10ZXN0cy5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsCiAgImNsaWVudF9pZCI6ICIx"
                    "MDk4NTYwMjgzNDI5MDI4ODI3MTUiLAogICJhdXRoX3VyaSI6ICJodHRwczovL2FjY291bnRzLmdvb2ds"
                    "ZS5jb20vby9vYXV0aDIvYXV0aCIsCiAgInRva2VuX3VyaSI6ICJodHRwczovL29hdXRoMi5nb29nbGVh"
                    "cGlzLmNvbS90b2tlbiIsCiAgImF1dGhfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3"
                    "dy5nb29nbGVhcGlzLmNvbS9vYXV0aDIvdjEvY2VydHMiLAogICJjbGllbnRfeDUwOV9jZXJ0X3VybCI6"
                    "ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9yb2JvdC92MS9tZXRhZGF0YS94NTA5L3NvbWUtc2Vy"
                    "dmljZS1hY2NvdW50JTQwZ2lmdGxlc3MtdGVzdHMuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iCn0K")


@pytest.fixture()
def storage_backend() -> Generator[GoogleCloudStorage, None, None]:
    """Provide a Google Cloud Storage backend for all GCS tests

    For this to work against production Google Cloud, you need to set
    ``GCP_ACCOUNT_KEY_FILE``, ``GCP_PROJECT_NAME`` and ``GCP_BUCKET_NAME``
    environment variables when running the tests.

    If these variables are not set, and pytest-vcr is not in use, the
    tests *will* fail.
    """
    account_key_file = os.environ.get('GCP_ACCOUNT_KEY_FILE')
    project_name = os.environ.get('GCP_PROJECT_NAME')
    bucket_name = os.environ.get('GCP_BUCKET_NAME')
    prefix = 'giftless-tests'

    if account_key_file and project_name and bucket_name:
        # We use a live GCS bucket to test
        storage = GoogleCloudStorage(project_name=project_name, bucket_name=bucket_name,
                                     account_key_file=account_key_file, path_prefix=prefix)
        try:
            yield storage
        finally:
            bucket = storage.storage_client.bucket(bucket_name)
            try:
                blobs = bucket.list_blobs(prefix=prefix + '/')
                bucket.delete_blobs(blobs)
            except GoogleAPIError as e:
                raise pytest.PytestWarning("Could not clean up after test: {}".format(e))
    else:
        yield GoogleCloudStorage(project_name=MOCK_GCP_PROJECT_NAME, bucket_name=MOCK_GCP_BUCKET_NAME,
                                 account_key_base64=MOCK_GCP_KEY_B64, path_prefix=prefix)


@pytest.fixture(scope='module')
def vcr_config():
    live_tests = bool(os.environ.get('GCP_ACCOUNT_KEY_FILE') and
                      os.environ.get('GCP_PROJECT_NAME') and
                      os.environ.get('GCP_BUCKET_NAME'))
    if live_tests:
        mode = 'once'
    else:
        mode = 'none'
    return {
        "filter_headers": [
            ('authorization', 'fake-authz-header')
        ],
        "record_mode": mode
    }


@pytest.mark.vcr()
class TestGoogleCloudStorageBackend(StreamingStorageAbstractTests, ExternalStorageAbstractTests):
    pass
