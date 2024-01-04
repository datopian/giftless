"""Representations define how to render a response for a given content-type

Most commonly this will convert data returned by views into JSON or a similar
format.

See http://flask-classful.teracy.org/#adding-resource-representations-get-real-classy-and-put-on-a-top-hat
"""
import json
from datetime import datetime
from functools import partial
from typing import Any

from flask import Response, make_response

GIT_LFS_MIME_TYPE = "application/vnd.git-lfs+json"


class CustomJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder that can support some additional required types"""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def output_json(
    data: Any,
    code: int | None,
    headers: dict[str, str] | None = None,
    content_type: str = "application/json",
) -> Response:
    dumped = json.dumps(data, cls=CustomJsonEncoder)
    if headers:
        headers.update({"Content-Type": content_type})
    else:
        headers = {"Content-Type": content_type}
    response = make_response(dumped, code, headers)
    return response


output_git_lfs_json = partial(output_json, content_type=GIT_LFS_MIME_TYPE)
