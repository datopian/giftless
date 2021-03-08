"""Tests for the Azure storage backend
"""
import os
from typing import Generator

import pytest

from giftless.storage.aws_s3 import AwsS3Storage

from . import ExternalStorageAbstractTests, StreamingStorageAbstractTests

MOCK_AWS_ACCESS_KEY_ID = '123123123'
MOCK_AWS_SECRET_ACCESS_KEY = 'abcabcabc'
MOCK_AWS_S3_BUCKET_NAME = 'fake_bucket'


@pytest.fixture()
def storage_backend() -> Generator[AwsS3Storage, None, None]:
    """Provide a Google Cloud Storage backend for all GCS tests

    For this to work against production Google Cloud, you need to set
    ``GCP_ACCOUNT_KEY_FILE``, ``GCP_PROJECT_NAME`` and ``GCP_BUCKET_NAME``
    environment variables when running the tests.

    If these variables are not set, and pytest-vcr is not in use, the
    tests *will* fail.
    """
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_s3_bucket_name = os.environ.get('AWS_S3_BUCKET_NAME')
    prefix = 'giftless-tests'

    if aws_s3_bucket_name and aws_access_key_id and aws_secret_access_key:
        # We use a live S3 bucket to test
        storage = AwsS3Storage(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,
                               aws_s3_bucket_name=aws_s3_bucket_name, path_prefix=prefix)
        try:
            yield storage
        finally:
            bucket = storage.storage_client.bucket(bucket_name)
            try:
                blobs = bucket.list_blobs(prefix=prefix + '/')
                bucket.delete_blobs(blobs)
            except Exception as e:
                raise pytest.PytestWarning("Could not clean up after test: {}".format(e))
    else:
        yield AwsS3Storage(aws_access_key_id=MOCK_AWS_ACCESS_KEY_ID, aws_secret_access_key=MOCK_AWS_SECRET_ACCESS_KEY,
                           aws_s3_bucket_name=MOCK_AWS_S3_BUCKET_NAME, path_prefix=prefix)


@pytest.fixture(scope='module')
def vcr_config():
    live_tests = bool(os.environ.get('AWS_ACCESS_KEY_ID') and
                      os.environ.get('AWS_SECRET_ACCESS_KEY') and
                      os.environ.get('AWS_S3_BUCKET_NAME'))
    if live_tests:
        mode = 'all'
    else:
        mode = 'none'
    return {
        "filter_headers": [
            ('authorization', 'fake-authz-header')
        ],
        "record_mode": mode
    }


@pytest.mark.vcr()
class TestAwsS3StorageBackend(StreamingStorageAbstractTests, ExternalStorageAbstractTests):
    pass
