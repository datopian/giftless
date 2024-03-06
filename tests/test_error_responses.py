"""Tests for schema definitions."""
from flask.testing import FlaskClient

from .helpers import batch_request_payload


def test_error_response_422(test_client: FlaskClient) -> None:
    """Test an invalid payload error."""
    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch",
        json=batch_request_payload(delete_keys=["operation"]),
    )

    assert response.status_code == 422
    assert response.content_type == "application/vnd.git-lfs+json"
    assert "message" in response.json  # type:ignore[operator]


def test_error_response_404(test_client: FlaskClient) -> None:
    """Test a bad route error."""
    response = test_client.get("/now/for/something/completely/different")

    assert response.status_code == 404
    assert response.content_type == "application/vnd.git-lfs+json"
    assert "message" in response.json  # type:ignore[operator]


def test_error_response_403(test_client: FlaskClient) -> None:
    """Test that we get Forbidden when trying to upload with the default
    read-only setup.
    """
    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch",
        json=batch_request_payload(operation="upload"),
    )

    assert response.status_code == 403
    assert response.content_type == "application/vnd.git-lfs+json"
    assert "message" in response.json  # type:ignore[operator]
