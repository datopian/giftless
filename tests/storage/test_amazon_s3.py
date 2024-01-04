"""Tests for the Azure storage backend
"""
import os
from base64 import b64decode
from binascii import unhexlify
from collections.abc import Generator
from typing import Any
import pytest

from giftless.storage import ExternalStorage
from giftless.storage.amazon_s3 import AmazonS3Storage

from . import (
    ARBITRARY_OID,
    ExternalStorageAbstractTests,
    StreamingStorageAbstractTests,
)

TEST_AWS_S3_BUCKET_NAME = "test-giftless"


@pytest.fixture
def storage_backend() -> Generator[AmazonS3Storage, None, None]:
    """Provide a S3 Storage backend for all AWS S3 tests

    For this to work against production S3, you need to set boto3 auth:
    1. AWS_ACCESS_KEY_ID
    2. AWS_SECRET_ACCESS_KEY

    For more details please see:
    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#environment-variables

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
            raise pytest.PytestWarning(f"Could not clean up after test: {e}")


@pytest.fixture(scope="module")
def vcr_config() -> dict[str,Any]:
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
    # This is gross.  Because we're extending the classes, it has to return
    # the same thing, and upload uses the test method and returns a value
    # which is not how tests usually work, and ugh.
    def test_get_upload_action(self, storage_backend: ExternalStorage) -> dict[str,Any]:
        upload = super().test_get_upload_action(storage_backend)

        assert upload["header"]["Content-Type"] == "application/octet-stream"

        b64_oid = upload["header"]["x-amz-checksum-sha256"]
        assert b64decode(b64_oid) == unhexlify(ARBITRARY_OID)
        return upload  # yuck
