"""Tests for schema definitions."""
from typing import cast

import pytest
from flask.testing import FlaskClient

from .helpers import batch_request_payload, create_file_in_storage


@pytest.mark.usefixtures("_authz_full_access")
def test_upload_batch_request(test_client: FlaskClient) -> None:
    """Test basic batch API with a basic successful upload request."""
    request_payload = batch_request_payload(operation="upload")
    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 200
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" not in payload
    assert payload["transfer"] == "basic"
    assert len(payload["objects"]) == 1

    obj = payload["objects"][0]
    assert obj["oid"] == request_payload["objects"][0]["oid"]
    assert obj["size"] == request_payload["objects"][0]["size"]
    assert len(obj["actions"]) == 2
    assert "upload" in obj["actions"]
    assert "verify" in obj["actions"]


def test_download_batch_request(
    test_client: FlaskClient, storage_path: str
) -> None:
    """Test basic batch API with a basic successful upload request."""
    request_payload = batch_request_payload(operation="download")
    oid = request_payload["objects"][0]["oid"]
    create_file_in_storage(storage_path, "myorg", "myrepo", oid, size=8)

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 200
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" not in payload
    assert payload["transfer"] == "basic"
    assert len(payload["objects"]) == 1

    obj = payload["objects"][0]
    assert obj["oid"] == request_payload["objects"][0]["oid"]
    assert obj["size"] == request_payload["objects"][0]["size"]
    assert len(obj["actions"]) == 1
    assert "download" in obj["actions"]


def test_download_batch_request_two_files_one_missing(
    test_client: FlaskClient, storage_path: str
) -> None:
    """Test batch API with a two object download request where one file 404."""
    request_payload = batch_request_payload(operation="download")
    oid = request_payload["objects"][0]["oid"]
    create_file_in_storage(storage_path, "myorg", "myrepo", oid, size=8)

    # Add a 2nd, non existing object
    request_payload["objects"].append({"oid": "12345679", "size": 5555})

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 200
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" not in payload
    assert payload["transfer"] == "basic"
    assert len(payload["objects"]) == 2

    obj = payload["objects"][0]
    assert obj["oid"] == request_payload["objects"][0]["oid"]
    assert obj["size"] == request_payload["objects"][0]["size"]
    assert len(obj["actions"]) == 1
    assert "download" in obj["actions"]

    obj = payload["objects"][1]
    assert obj["oid"] == request_payload["objects"][1]["oid"]
    assert obj["size"] == request_payload["objects"][1]["size"]
    assert "actions" not in obj
    assert obj["error"]["code"] == 404


def test_download_batch_request_two_files_missing(
    test_client: FlaskClient,
) -> None:
    """Test batch API with a two object download request where both files
    404.
    """
    request_payload = batch_request_payload(operation="download")
    request_payload["objects"].append({"oid": "12345679", "size": 5555})

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 404
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" in payload
    assert "objects" not in payload
    assert "transfer" not in payload


def test_download_batch_request_two_files_one_mismatch(
    test_client: FlaskClient, storage_path: str
) -> None:
    """Test batch API with a two object download request where one file 422."""
    request_payload = batch_request_payload(operation="download")
    request_payload["objects"].append({"oid": "12345679", "size": 8})

    create_file_in_storage(
        storage_path,
        "myorg",
        "myrepo",
        request_payload["objects"][0]["oid"],
        size=8,
    )
    create_file_in_storage(
        storage_path,
        "myorg",
        "myrepo",
        request_payload["objects"][1]["oid"],
        size=9,
    )

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 200
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" not in payload
    assert payload["transfer"] == "basic"
    assert len(payload["objects"]) == 2

    obj = payload["objects"][0]
    assert obj["oid"] == request_payload["objects"][0]["oid"]
    assert obj["size"] == request_payload["objects"][0]["size"]
    assert len(obj["actions"]) == 1
    assert "download" in obj["actions"]

    obj = payload["objects"][1]
    assert obj["oid"] == request_payload["objects"][1]["oid"]
    assert obj["size"] == request_payload["objects"][1]["size"]
    assert "actions" not in obj
    assert obj["error"]["code"] == 422


def test_download_batch_request_one_file_mismatch(
    test_client: FlaskClient, storage_path: str
) -> None:
    """Test batch API with a one object download request where the file 422."""
    request_payload = batch_request_payload(operation="download")
    create_file_in_storage(
        storage_path,
        "myorg",
        "myrepo",
        request_payload["objects"][0]["oid"],
        size=9,
    )

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 422
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" in payload
    assert "objects" not in payload
    assert "transfer" not in payload


def test_download_batch_request_two_files_different_errors(
    test_client: FlaskClient, storage_path: str
) -> None:
    """Test batch API with a two object download request where one file is
    missing and one is mismatch.
    """
    request_payload = batch_request_payload(operation="download")
    request_payload["objects"].append({"oid": "12345679", "size": 8})
    create_file_in_storage(
        storage_path,
        "myorg",
        "myrepo",
        request_payload["objects"][0]["oid"],
        size=9,
    )

    response = test_client.post(
        "/myorg/myrepo.git/info/lfs/objects/batch", json=request_payload
    )

    assert response.status_code == 422
    assert response.content_type == "application/vnd.git-lfs+json"

    payload = cast(dict, response.json)
    assert "message" in payload
    assert "objects" not in payload
    assert "transfer" not in payload
