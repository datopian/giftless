"""Representations define how to render a response for a given content-type

Most commonly this will convert data returned by views into JSON or a similar
format.

See http://flask-classful.teracy.org/#adding-resource-representations-get-real-classy-and-put-on-a-top-hat
"""
import json
from datetime import datetime

from flask import make_response


class CustomJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder that can support some additional required types
    """
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def output_json(data, code, headers=None):
    content_type = 'application/json'

    dumped = json.dumps(data, cls=CustomJsonEncoder)
    if headers:
        headers.update({'Content-Type': content_type})
    else:
        headers = {'Content-Type': content_type}
    response = make_response(dumped, code, headers)
    return response
