"""Tests for schema definitions
"""
import pytest

from .helpers import batch_request_payload, create_file_in_storage


@pytest.mark.usefixtures('authz_full_access')
def test_upload_batch_request(test_client):
    """Test basic batch API with a basic successful upload request
    """
    request_payload = batch_request_payload(operation='upload')
    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 200 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' not in payload
    assert payload['transfer'] == 'basic'
    assert len(payload['objects']) == 1

    object = payload['objects'][0]
    assert object['oid'] == request_payload['objects'][0]['oid']
    assert object['size'] == request_payload['objects'][0]['size']
    assert len(object['actions']) == 2
    assert 'upload' in object['actions']
    assert 'verify' in object['actions']


def test_download_batch_request(test_client, storage_path):
    """Test basic batch API with a basic successful upload request
    """
    request_payload = batch_request_payload(operation='download')
    oid = request_payload['objects'][0]['oid']
    create_file_in_storage(storage_path, 'myorg', 'myrepo', oid, size=8)

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 200 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' not in payload
    assert payload['transfer'] == 'basic'
    assert len(payload['objects']) == 1

    object = payload['objects'][0]
    assert object['oid'] == request_payload['objects'][0]['oid']
    assert object['size'] == request_payload['objects'][0]['size']
    assert len(object['actions']) == 1
    assert 'download' in object['actions']


def test_download_batch_request_two_files_one_missing(test_client, storage_path):
    """Test batch API with a two object download request where one file 404
    """
    request_payload = batch_request_payload(operation='download')
    oid = request_payload['objects'][0]['oid']
    create_file_in_storage(storage_path, 'myorg', 'myrepo', oid, size=8)

    # Add a 2nd, non existing object
    request_payload['objects'].append({
        "oid": "12345679",
        "size": 5555
    })

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 200 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' not in payload
    assert payload['transfer'] == 'basic'
    assert len(payload['objects']) == 2

    object = payload['objects'][0]
    assert object['oid'] == request_payload['objects'][0]['oid']
    assert object['size'] == request_payload['objects'][0]['size']
    assert len(object['actions']) == 1
    assert 'download' in object['actions']

    object = payload['objects'][1]
    assert object['oid'] == request_payload['objects'][1]['oid']
    assert object['size'] == request_payload['objects'][1]['size']
    assert 'actions' not in object
    assert object['error']['code'] == 404


def test_download_batch_request_two_files_missing(test_client):
    """Test batch API with a two object download request where one file 404
    """
    request_payload = batch_request_payload(operation='download')
    request_payload['objects'].append({
        "oid": "12345679",
        "size": 5555
    })

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 404 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' in payload
    assert 'objects' not in payload
    assert 'transfer' not in payload


def test_download_batch_request_two_files_one_mismatch(test_client, storage_path):
    """Test batch API with a two object download request where one file 422
    """
    request_payload = batch_request_payload(operation='download')
    request_payload['objects'].append({
        "oid": "12345679",
        "size": 8
    })

    create_file_in_storage(storage_path, 'myorg', 'myrepo', request_payload['objects'][0]['oid'], size=8)
    create_file_in_storage(storage_path, 'myorg', 'myrepo', request_payload['objects'][1]['oid'], size=9)

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 200 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' not in payload
    assert payload['transfer'] == 'basic'
    assert len(payload['objects']) == 2

    object = payload['objects'][0]
    assert object['oid'] == request_payload['objects'][0]['oid']
    assert object['size'] == request_payload['objects'][0]['size']
    assert len(object['actions']) == 1
    assert 'download' in object['actions']

    object = payload['objects'][1]
    assert object['oid'] == request_payload['objects'][1]['oid']
    assert object['size'] == request_payload['objects'][1]['size']
    assert 'actions' not in object
    assert object['error']['code'] == 422


def test_download_batch_request_one_file_mismatch(test_client, storage_path):
    """Test batch API with a two object download request where one file 422
    """
    request_payload = batch_request_payload(operation='download')
    create_file_in_storage(storage_path, 'myorg', 'myrepo', request_payload['objects'][0]['oid'], size=9)

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 422 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' in payload
    assert 'objects' not in payload
    assert 'transfer' not in payload


def test_download_batch_request_two_files_different_errors(test_client, storage_path):
    """Test batch API with a two object download request where one file is missing and one is mismatch
    """
    request_payload = batch_request_payload(operation='download')
    request_payload['objects'].append({
        "oid": "12345679",
        "size": 8
    })
    create_file_in_storage(storage_path, 'myorg', 'myrepo', request_payload['objects'][0]['oid'], size=9)

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 422 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type

    payload = response.json
    assert 'message' in payload
    assert 'objects' not in payload
    assert 'transfer' not in payload
