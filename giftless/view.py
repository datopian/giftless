"""Flask-Classful View Classes
"""
from typing import Any, Dict, Optional

from flask_classful import FlaskView
from webargs.flaskparser import parser  # type: ignore

from giftless import exc, representation, schema, transfer
from giftless.auth import authentication as authn
from giftless.auth.identity import Permission


class BaseView(FlaskView):
    """This extends on Flask-Classful's base view class to add some common custom
    functionality
    """

    decorators = [authn.login_required]

    representations = {'application/json': representation.output_json,
                       representation.GIT_LFS_MIME_TYPE: representation.output_git_lfs_json,
                       'flask-classful/default': representation.output_git_lfs_json}

    trailing_slash = False

    @classmethod
    def register(cls, *args, **kwargs):
        if kwargs.get('base_class') is None:
            kwargs['base_class'] = BaseView
        return super().register(*args, **kwargs)

    @classmethod
    def _check_authorization(cls, organization, repo, permission, oid=None):
        """Check the current user is authorized to perform an action and raise an exception otherwise
        """
        if not cls._is_authorized(organization, repo, permission, oid):
            raise exc.Forbidden("Your are not authorized to perform this action")

    @staticmethod
    def _is_authorized(organization, repo, permission, oid=None):
        """Check the current user is authorized to perform an action
        """
        identity = authn.get_identity()
        return identity and identity.is_authorized(organization, repo, permission, oid)


class BatchView(BaseView):
    """Batch operations
    """
    route_base = '<organization>/<repo>/objects/batch'

    def post(self, organization, repo):
        """Batch operations
        """
        payload = parser.parse(schema.batch_request_schema)

        try:
            transfer_type, adapter = transfer.match_transfer_adapter(payload['transfers'])
        except ValueError as e:
            raise exc.InvalidPayload(e)

        permission = Permission.WRITE if payload['operation'] == schema.Operation.upload else Permission.READ
        try:
            self._check_authorization(organization, repo, permission)
        except exc.Forbidden:
            # User doesn't have global permission to the entire namespace, but may be authorized for all objects
            if not all(self._is_authorized(organization, repo, permission, o['oid']) for o in payload['objects']):
                raise

        response = {"transfer": transfer_type}
        action = adapter.get_action(payload['operation'].value, organization, repo)
        response['objects'] = [action(**o) for o in payload['objects']]

        if all(self._is_error(o, 404) for o in response['objects']):
            raise exc.NotFound("Cannot find any of the requested objects")

        if all(self._is_error(o) for o in response['objects']):
            raise exc.InvalidPayload("Cannot validate any of the requested objects")

        # TODO: Check Accept header
        # TODO: do we need an output schema?

        return response

    @staticmethod
    def _is_error(obj: Dict[str, Any], code: Optional[int] = None):
        try:
            return obj['error']['code'] == code or code is None
        except KeyError:
            return False


class ViewProvider:
    """ViewProvider is a marker interface for storage and transfer adapters that can provide their own Flask views

    This allows transfer and storage backends to register routes for accessing or verifying files, for example,
    directly from the Giftless HTTP server.
    """
    def register_views(self, app):
        pass
