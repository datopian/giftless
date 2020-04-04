"""Tests for schema definitions
"""
from .helpers import batch_request_payload


def test_error_response_422(test_client):
    """Test an invalid payload error
    """
    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=batch_request_payload(delete_keys=['operation']))

    assert 422 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type
    assert 'message' in response.json


def test_error_response_404(test_client):
    """Test a bad route error
    """
    response = test_client.get('/now/for/something/completely/different')

    assert 404 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type
    assert 'message' in response.json


def test_error_response_403(test_client):
    """Test that we get Forbidden when trying to upload with the default read-only setup
    """
    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=batch_request_payload(operation='upload'))

    assert 403 == response.status_code
    assert 'application/vnd.git-lfs+json' == response.content_type
    assert 'message' in response.json
