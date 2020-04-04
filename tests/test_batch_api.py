"""Tests for schema definitions
"""
import pytest

from .helpers import batch_request_payload, create_file_in_storage


@pytest.mark.usefixtures('authz_full_access')
def test_upload_batch_request(test_client):
    """Test an invalid payload error
    """
    # app_config.update({"AUTHENTICATORS": [
    #     'giftless.auth.allow_anon:read_write'
    # ]})

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
    """Test an invalid payload error
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
