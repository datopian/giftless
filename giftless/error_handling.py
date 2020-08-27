"""Handle errors according to the Git LFS spec

See https://github.com/git-lfs/git-lfs/blob/master/docs/api/batch.md#response-errors
"""
from werkzeug.exceptions import default_exceptions

from .representation import output_git_lfs_json


class ApiErrorHandler:

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        for code in default_exceptions:
            app.errorhandler(code)(self.error_as_json)

    @classmethod
    def error_as_json(cls, ex):
        """Handle errors by returning a JSON response
        """
        code = ex.code if hasattr(ex, 'code') else 500
        data = {"message": str(ex)}

        return output_git_lfs_json(data=data, code=code)
