"""Flask-Classful View Classes
"""
from flask_classful import FlaskView

from . import representation


class _BaseView(FlaskView):
    """This extends on Flask-Classful's base view class to add some common custom
    functionality
    """
    representations = {'application/json': representation.output_json,
                       'flask-classful/default': representation.output_json}

    trailing_slash = False

    @classmethod
    def register(cls, app, route_base=None, subdomain=None, route_prefix=None, trailing_slash=None,
                 method_dashified=None, base_class=None, **rule_options):
        if base_class is None:
            base_class = _BaseView
        return super().register(app, route_base, subdomain, route_prefix, trailing_slash, method_dashified, base_class,
                                **rule_options)


class BatchView(_BaseView):
    pass


def register_all(app):
    """Register all views with the Flask app
    """
    for v in (v for v in globals() if isinstance(v, _BaseView)):
        v.register(app)
