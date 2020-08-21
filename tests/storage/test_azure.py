"""Tests for the Azure storage backend
"""
import os
from typing import Generator

import pytest
from azure.core.exceptions import AzureError  # type: ignore
from azure.storage.blob import BlobServiceClient  # type: ignore

from giftless.storage.azure import AzureBlobsStorage

from . import ExternalStorageAbstractTests, StreamingStorageAbstractTests

MOCK_AZURE_ACCOUNT_NAME = 'my-account'
MOCK_AZURE_CONTAINER_NAME = 'my-container'


@pytest.fixture()
def storage_backend() -> Generator[AzureBlobsStorage, None, None]:
    """Provide an Azure Blob Storage backend for all Azure tests

    For this to work against production Azure, you need to set ``AZURE_CONNECTION_STRING``
    and ``AZURE_CONTAINER`` environment variables when running the tests.

    If these variables are not set, and pytest-vcr is not in use, the tests *will* fail.
    """
    connection_str = os.environ.get('AZURE_CONNECTION_STRING')
    container_name = os.environ.get('AZURE_CONTAINER')
    prefix = 'giftless-tests'

    if container_name and connection_str:
        # We use a live Azure container to test
        client = BlobServiceClient.from_connection_string(connection_str)
        try:
            yield AzureBlobsStorage(connection_str, container_name, path_prefix=prefix)
        finally:
            container = client.get_container_client(container_name)
            try:
                for blob in container.list_blobs(name_starts_with=prefix):
                    container.delete_blob(blob)
            except AzureError:
                pass
    else:
        connection_str = f'DefaultEndpointsProtocol=https;AccountName={MOCK_AZURE_ACCOUNT_NAME};' \
                          'AccountKey=U29tZVJhbmRvbUNyYXBIZXJlCg==;EndpointSuffix=core.windows.net'
        yield AzureBlobsStorage(connection_str, MOCK_AZURE_CONTAINER_NAME, path_prefix=prefix)


@pytest.fixture(scope='module')
def vcr_config():
    live_tests = bool(os.environ.get('AZURE_CONNECTION_STRING') and os.environ.get('AZURE_CONTAINER'))
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
class TestAzureBlobStorageBackend(StreamingStorageAbstractTests, ExternalStorageAbstractTests):
    pass
