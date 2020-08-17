"""Tests for the local storage backend
"""
import os
import random
from string import ascii_letters
from typing import Generator

import pytest
from azure.core.exceptions import AzureError  # type: ignore
from azure.storage.blob import BlobServiceClient  # type: ignore

from giftless.storage.azure import AzureBlobsStorage

from . import StreamingStorageAbstractTests


@pytest.fixture()
def storage_backend() -> Generator[AzureBlobsStorage, None, None]:
    """Provide an Azure Blob Storage backend for all Azure tests

    For this to work against production Azure, you need to set ``AZURE_CONNECTION_STRING``
    and ``AZURE_CONTAINER`` environment variables when running the tests.

    If these variables are not set, and pytest-vcr is not in use, the tests *will* fail.
    """
    connection_str = os.environ.get('AZURE_CONNECTION_STRING', '')
    container_name = os.environ.get('AZURE_CONTAINER', '')
    prefix = 'giftless-tests-{}'.format(''.join(random.choices(ascii_letters, k=8)))

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


class TestAzureBlobStorageBackend(StreamingStorageAbstractTests):
    pass