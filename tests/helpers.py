"""Test helpers."""
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import flask


def batch_request_payload(
    delete_keys: Sequence[str] = (), **kwargs: Any
) -> dict[str, Any]:
    """Generate sample batch request payload."""
    payload = {
        "operation": "download",
        "transfers": ["basic"],
        "ref": {"name": "refs/heads/master"},
        "objects": [{"oid": "12345678", "size": 8}],
    }

    for key in delete_keys:
        del payload[key]

    payload.update(kwargs)
    return payload


def create_file_in_storage(
    storage_path: str, org: str, repo: str, filename: str, size: int = 1
) -> None:
    """Put a dummy file in the storage path for a specific org / repo
    / oid combination.

    This is useful where we want to test download / verify actions
    without relying on 'put' actions to work.

    This assumes cleanup is done somewhere else (e.g. in the
    'storage_path' fixture).
    """
    repo_path = Path(storage_path) / org / repo
    repo_path.mkdir(parents=True, exist_ok=True)
    with Path(repo_path / filename).open("wb") as f:
        for c in (b"0" for _ in range(size)):
            f.write(c)


def legacy_endpoints_id(enabled: bool) -> str:
    return "legacy-ep" if enabled else "current-ep"


def expected_uri_prefix(app: flask.Flask, *args: str) -> str:
    core_prefix = "/".join(args)
    if not app.config.get("LEGACY_ENDPOINTS"):
        return core_prefix + ".git/info/lfs"
    return core_prefix
