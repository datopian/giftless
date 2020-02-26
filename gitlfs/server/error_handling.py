"""Handle errors by returning RFC-7808 (Problem Details for HTTP APIs) error payload
"""
from typing import Any, Dict

from flask import jsonify
from werkzeug.exceptions import default_exceptions


class ApiErrorHandler:

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        for code in default_exceptions:
            app.errorhandler(code)(self.app_api_problem_json)

    @classmethod
    def app_api_problem_json(cls, ex):
        """Generic application/problem+json error handler
        """
        code = ex.code if hasattr(ex, 'code') else 500
        data = {"type": "http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html",
                "title": ex.name if hasattr(ex, 'name') else "Internal Server Error",
                "detail": ex.description if hasattr(ex, 'description') else str(ex),
                "status": code}

        if hasattr(ex, 'exc'):
            data.update(cls._extract_extra_data(ex.exc))

        response = jsonify(data)
        response.headers['Content-Type'] = 'application/problem+json'
        response.status_code = code

        return response

    @classmethod
    def _extract_extra_data(cls, exception: Any) -> Dict[str, Any]:
        """Extract additional information fields from exception
        """
        extra_data = {}
        if hasattr(exception, 'messages'):
            extra_data['messages'] = exception.messages

        return extra_data
