"""Test helpers
"""


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
                "size": 123
            }
        ]
    }

    for key in delete_keys:
        del payload[key]

    payload.update(kwargs)
    return payload
