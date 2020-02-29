"""Flask-Classful View Classes
"""
from flask_classful import FlaskView
from webargs.flaskparser import parser  # type: ignore
from werkzeug.exceptions import UnprocessableEntity

from giftless import representation, schema, transfer


class BaseView(FlaskView):
    """This extends on Flask-Classful's base view class to add some common custom
    functionality
    """
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
            raise UnprocessableEntity(e)

        response = {"transfer": transfer_type}
        action = adapter.get_action(payload['operation'].value, organization, repo)
        response['objects'] = [action(**o) for o in payload['objects']]

        # TODO: Check if *all* objects have errors and if so return 422
        # TODO: Check Accept header
        # TODO: do we need an output schema?

        return response
