"""Configuration handling helper functions and default configuration
"""
import os
from typing import Dict

import figcan
import yaml

ENV_PREFIX = 'GITLFS_'

default_config = {
    "JWT_ALGORITHM": 'HS256',
    "JWT_SECRET_KEY": None,
}


def configure(app, additional_config: Dict = None):
    """Configure a Flask app using Figcan managed configuration object
    """
    config = _compose_config()
    app.config.update(config)
    if additional_config:
        app.config.update(additional_config)
    return app


def _compose_config():
    """Compose configuration object from all available sources
    """
    config = figcan.Configuration(default_config)
    if os.environ.get(f'{ENV_PREFIX}CONFIG_FILE'):
        with open(os.environ.get(f'{ENV_PREFIX}CONFIG_FILE')) as f:
            config.apply(yaml.safe_load(f))
        os.environ.pop(f'{ENV_PREFIX}CONFIG_FILE')
    config.apply_flat(os.environ, prefix=ENV_PREFIX)
