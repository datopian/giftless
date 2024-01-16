"""Handle errors according to the Git LFS spec.

See https://github.com/git-lfs/git-lfs/blob/master/docs\
/api/batch.md#response-errors
"""
from flask import Flask, Response
from werkzeug.exceptions import default_exceptions

from .representation import output_git_lfs_json


class ApiErrorHandler:
    """Handler to send JSON response for errors."""

    def __init__(self, app: Flask | None = None) -> None:
        if app:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        for code in default_exceptions:
            app.errorhandler(code)(self.error_as_json)

    @classmethod
    def error_as_json(cls, ex: Exception) -> Response:
        """Handle errors by returning a JSON response."""
        code = ex.code if hasattr(ex, "code") else 500
        data = {"message": str(ex)}

        return output_git_lfs_json(data=data, code=code)
