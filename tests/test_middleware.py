"""Tests for using middleware and some specific middleware."""
from typing import Any, cast

import flask
import pytest
from flask.testing import FlaskClient

from giftless.app import init_app

from .helpers import (
    batch_request_payload,
    expected_uri_prefix,
    legacy_endpoints_id,
)


@pytest.fixture
def app(storage_path: str) -> flask.Flask:
    """Session fixture to configure the Flask app."""
    return init_app(
        additional_config={
            "TESTING": True,
            "TRANSFER_ADAPTERS": {
                "basic": {
                    "options": {"storage_options": {"path": storage_path}}
                }
            },
            "MIDDLEWARE": [
                {
                    "class": "werkzeug.middleware.proxy_fix:ProxyFix",
                    "kwargs": {
                        "x_host": 1,
                        "x_port": 1,
                        "x_prefix": 1,
                    },
                }
            ],
        }
    )


@pytest.mark.usefixtures("_authz_full_access")
@pytest.mark.parametrize(
    "app", [False, True], ids=legacy_endpoints_id, indirect=True
)
def test_upload_request_with_x_forwarded_middleware(
    app: flask.Flask,
    test_client: FlaskClient,
) -> None:
    """Test the ProxyFix middleware generates correct URLs if
    X-Forwarded headers are set.
    """
    request_payload = batch_request_payload(operation="upload")
    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 200
    json = cast(dict[str, Any], response.json)
    upload_action = json["objects"][0]["actions"]["upload"]
    href = upload_action["href"]
    exp_uri_prefix = expected_uri_prefix(app, "myorg", "myrepo")
    assert (
        href == f"http://localhost/{exp_uri_prefix}/objects/storage/12345678"
    )

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch",
        json=request_payload,
        headers={
            "X-Forwarded-Host": "mycompany.xyz",
            "X-Forwarded-Port": "1234",
            "X-Forwarded-Prefix": "/lfs",
            "X-Forwarded-Proto": "https",
        },
    )

    assert response.status_code == 200
    json = cast(dict[str, Any], response.json)
    upload_action = json["objects"][0]["actions"]["upload"]
    href = upload_action["href"]
    assert (
        href
        == f"https://mycompany.xyz:1234/lfs/{exp_uri_prefix}/objects/storage/12345678"
    )
