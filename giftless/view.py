"""Flask-Classful View Classes
"""
from typing import Any, Dict

from flask_classful import FlaskView
from webargs.flaskparser import parser  # type: ignore

from giftless import exc, representation, schema, transfer
from giftless.auth import authentication as authn
from giftless.auth.identity import Permission
from giftless.jwt import JWT
from giftless.transfer import TransferAdapter


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
    def register(cls, app, route_base=None, subdomain=None, route_prefix=None, trailing_slash=None,
                 method_dashified=None, base_class=None, **rule_options):
        if base_class is None:
            base_class = BaseView
        return super().register(app, route_base, subdomain, route_prefix, trailing_slash, method_dashified, base_class,
                                **rule_options)

    def _check_authorization(self, organization, repo, permission, oid=None):
        """Check the current user is authorized to perform an action
        """
        if not authn.get_identity().is_authorized(organization, repo, permission, oid):
            raise exc.Forbidden("Your are not authorized to perform this action")


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
        self._check_authorization(organization, repo, permission)

        response = {"transfer": transfer_type}
        action = adapter.get_action(payload['operation'].value, organization, repo)
        response['objects'] = [self._sign_actions(adapter, action(**o)) for o in payload['objects']]

        # TODO: Check if *all* objects have errors and if so return 422
        # TODO: Check Accept header
        # TODO: do we need an output schema?

        return response

    def _sign_actions(self, adapter: TransferAdapter, object: Dict[str, Any]):
        """Sign object actions using JWT token if we need to and JWT is configured
        """
        if not adapter.presign_actions:
            return object

        for action_name, action_spec in object['actions'].items():
            if action_name in adapter.presign_actions:
                headers = action_spec.get('header', {})
                if 'Authorization' in headers or 'authorization' in headers:
                    continue

                token = JWT.token('foobaz')
                if token is None:
                    continue

                headers['Authorization'] = f'Bearer {token}'
                action_spec['header'] = headers
                action_spec['expires_in'] = JWT.lifetime()

        object['authenticated'] = True

        return object
