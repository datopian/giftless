"""Test helpers
"""
import os


def batch_request_payload(delete_keys=(), **kwargs):
    """Generate sample batch request payload
    """
    payload = {
        "operation": "download",
        "transfers": ["basic"],
        "ref": {"name": "refs/heads/master"},
        "objects": [
            {
                "oid": "12345678",
                "size": 8
            }
        ]
    }

    for key in delete_keys:
        del payload[key]

    payload.update(kwargs)
    return payload


def create_file_in_storage(storage_path, org, repo, filename, size=1):
    """Put a dummy file in the storage path for a specific org / repo / oid combination

    This is useful where we want to test download / verify actions without relying on
    'put' actions to work

    This assumes cleanup is done somewhere else (e.g. in the 'storage_path' fixture)
    """
    repo_path = os.path.join(storage_path, org, repo)
    os.makedirs(repo_path, exist_ok=True)
    with open(os.path.join(repo_path, filename), 'wb') as f:
        for c in (b'0' for _ in range(size)):
            f.write(c)
