"""Tests for using middleware and some specific middleware
"""
import pytest

from giftless.app import init_app

from .helpers import batch_request_payload


@pytest.fixture()
def app(storage_path):
    """Session fixture to configure the Flask app
    """
    app = init_app(additional_config={
        "TESTING": True,
        "TRANSFER_ADAPTERS": {
            "basic": {
                "options": {
                    "storage_options": {
                        "path": storage_path
                    }
                }
            }
        },
        "MIDDLEWARE": [
            {
                "class": "werkzeug.middleware.proxy_fix:ProxyFix",
                "kwargs": {
                    "x_host": 1,
                    "x_port": 1,
                    "x_prefix": 1,
                }
            }
        ]
    })
    return app


@pytest.mark.usefixtures('authz_full_access')
def test_upload_request_with_x_forwarded_middleware(test_client):
    """Test the ProxyFix middleware generates correct URLs if X-Forwarded headers are set
    """
    request_payload = batch_request_payload(operation='upload')
    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload)

    assert 200 == response.status_code
    href = response.json['objects'][0]['actions']['upload']['href']
    assert 'http://localhost/myorg/myrepo/objects/storage/12345678' == href

    response = test_client.post('/myorg/myrepo/objects/batch',
                                json=request_payload,
                                headers={
                                    'X-Forwarded-Host': 'mycompany.xyz',
                                    'X-Forwarded-Port': '1234',
                                    'X-Forwarded-Prefix': '/lfs',
                                    'X-Forwarded-Proto': 'https'
                                })

    assert 200 == response.status_code
    href = response.json['objects'][0]['actions']['upload']['href']
    assert 'https://mycompany.xyz:1234/lfs/myorg/myrepo/objects/storage/12345678' == href
