"""Tests for the Azure storage backend."""
import os
from base64 import b64decode
from binascii import unhexlify
from collections.abc import Generator
from typing import Any

import pytest

from giftless.storage import ExternalStorage
from giftless.storage.amazon_s3 import AmazonS3Storage

from . import ExternalStorageAbstractTests, StreamingStorageAbstractTests

ARBITRARY_OID = (
    "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
)
TEST_AWS_S3_BUCKET_NAME = "test-giftless"


@pytest.fixture
def storage_backend() -> Generator[AmazonS3Storage, None, None]:
    """Provide a S3 Storage backend for all AWS S3 tests.

    For this to work against production S3, you need to set boto3 auth:
    1. AWS_ACCESS_KEY_ID
    2. AWS_SECRET_ACCESS_KEY

    For more details please see:
    https://boto3.amazonaws.com/v1/documentation/api/latest/
      guide/credentials.html#environment-variables

    If these variables are not set, and pytest-vcr is not in use, the
    tests *will* fail.
    """
    prefix = "giftless-tests"

    # We use a live S3 bucket to test
    storage = AmazonS3Storage(
        bucket_name=TEST_AWS_S3_BUCKET_NAME, path_prefix=prefix
    )
    try:
        yield storage
    finally:
        bucket = storage.s3.Bucket(TEST_AWS_S3_BUCKET_NAME)
        try:
            bucket.objects.all().delete()
        except Exception as e:
            raise pytest.PytestWarning(
                f"Could not clean up after test: {e}"
            ) from None


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    live_tests = bool(
        os.environ.get("AWS_ACCESS_KEY_ID")
        and os.environ.get("AWS_SECRET_ACCESS_KEY")
    )
    if live_tests:
        mode = "once"
    else:
        os.environ["AWS_ACCESS_KEY_ID"] = "fake"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "fake"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        mode = "none"
    return {
        "filter_headers": [("authorization", "fake-authz-header")],
        "record_mode": mode,
    }


@pytest.mark.vcr
class TestAmazonS3StorageBackend(
    StreamingStorageAbstractTests, ExternalStorageAbstractTests
):
    def test_get_upload_action(self, storage_backend: ExternalStorage) -> None:
        # A little duplication is better than a test that returns a value.
        action_spec = storage_backend.get_upload_action(
            "org/repo", ARBITRARY_OID, 100, 3600
        )
        upload = action_spec["actions"]["upload"]
        assert upload["href"][0:4] == "http"
        assert upload["expires_in"] == 3600
        assert upload["header"]["Content-Type"] == "application/octet-stream"

        b64_oid = upload["header"]["x-amz-checksum-sha256"]
        assert b64decode(b64_oid) == unhexlify(ARBITRARY_OID)
