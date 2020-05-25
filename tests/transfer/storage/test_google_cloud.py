"""Tests targeting GPC external storage
"""
import os
from unittest.mock import patch

import mock
from google.cloud import storage  # type: ignore


def mocked_gcp():
    storage_client_mock = mock.create_autospec(storage.Client)
    mock_bucket = mock.create_autospec(storage.Bucket)
    mock_blob = mock.create_autospec(storage.Blob)
    mock_bucket.return_value = mock_blob
    storage_client_mock.get_bucket.return_value = mock_bucket
    mock_bucket.get_blob.return_value = mock_blob
    mock_blob.download_as_string.return_value.decode.return_value = "file_content"
    attrs = {'put.return_value': 500,
             'exists.return_value': True, 'get_size.return_value': 500}
    patcher = patch('giftless.transfer.storage.google_cloud.GoogleCloudBlobStorage',
                    bucket_name="datahub-test", storage_client=storage_client_mock, **attrs)
    return patcher


def test_gcp_put():
    patcher = mocked_gcp()
    gcp = patcher.start()
    with open((os.path.join(os.path.dirname(__file__), 'data', 'test.csv')), "rb") as my_file:
        assert gcp.put("files", "research_data_factors.csv", my_file) == 500
    patcher.stop()


def test_gcp_exists():
    patcher = mocked_gcp()
    gcp = patcher.start()
    assert(gcp.exists("files", "data.csv")) is True
    patcher.stop()


def test_get_size():
    patcher = mocked_gcp()
    gcp = patcher.start()
    assert gcp.get_size("files", "data.csv") == 500
    patcher.stop()
