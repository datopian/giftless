"""Main Flask application initialization code
"""
from flask import Flask
from flask_marshmallow import Marshmallow  # type: ignore

from . import config, transfer, view
from .error_handling import ApiErrorHandler
from .jwt import jwt


def init_app(app=None, additional_config=None):
    """Flask app initialization
    """
    if app is None:
        app = Flask(__name__)

    config.configure(app, additional_config=additional_config)

    ApiErrorHandler(app)
    Marshmallow(app)
    jwt.init_app(app)

    view.BatchView.register(app)

    # TODO: configure authentication

    # Load configured transfer adapters
    transfer.init_flask_app(app)

    return app
