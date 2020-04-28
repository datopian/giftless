"""Main Flask application initialization code
"""
import logging
import os

from flask import Flask
from flask_marshmallow import Marshmallow  # type: ignore

from giftless import config, transfer, view

from .auth import authentication
from .error_handling import ApiErrorHandler


def init_app(app=None, additional_config=None):
    """Flask app initialization
    """
    if app is None:
        app = Flask(__name__)

    config.configure(app, additional_config=additional_config)

    if os.environ.get('GIFTLESS_DEBUG'):
        level = logging.DEBUG
    else:
        level = logging.WARNING

    logging.basicConfig(format='%(asctime)-15s %(name)-15s %(levelname)s %(message)s',
                        level=level)

    ApiErrorHandler(app)
    Marshmallow(app)

    authentication.init_app(app)

    view.BatchView.register(app)

    # Load configured transfer adapters
    transfer.init_flask_app(app)

    return app
