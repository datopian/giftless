"""Flask-Classful View Classes
"""
from flask_classful import FlaskView

from . import representation

# _view_classes = []


class BaseView(FlaskView):
    """This extends on Flask-Classful's base view class to add some common custom
    functionality
    """
    representations = {'application/json': representation.output_json,
                       'flask-classful/default': representation.output_json}

    trailing_slash = False

    # def __init_subclass__(cls, **kwargs):
    #     _view_classes.append(cls)

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
        return ["batch", organization, repo]


# def register_all(app):
#     """Register all views with the Flask app
#     """
#     log = logging.getLogger(__name__)
#     for v in _view_classes:
#         log.debug("Registering view class %s at %s", v.__class__.__name__, v.get_route_base())
#         v.register(app)
