"""Representations define how to render a response for a given content-type

Most commonly this will convert data returned by views into JSON or a similar
format.

See http://flask-classful.teracy.org/#adding-resource-representations-get-real-classy-and-put-on-a-top-hat
"""
import json
from datetime import datetime
from functools import partial

from flask import make_response

GIT_LFS_MIME_TYPE = 'application/vnd.git-lfs+json'


class CustomJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder that can support some additional required types
    """
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def output_json(data, code, headers=None, content_type='application/json'):
    dumped = json.dumps(data, cls=CustomJsonEncoder)
    if headers:
        headers.update({'Content-Type': content_type})
    else:
        headers = {'Content-Type': content_type}
    response = make_response(dumped, code, headers)
    return response


output_git_lfs_json = partial(output_json, content_type=GIT_LFS_MIME_TYPE)
