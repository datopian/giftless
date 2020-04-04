"""Configuration handling helper functions and default configuration
"""
import os
from typing import Dict, Optional

import figcan
import yaml

ENV_PREFIX = 'GIFTLESS_'

default_transfer_config = {
    "basic": figcan.Extensible({
        "factory": "giftless.transfer.basic_streaming:factory",
        "options": figcan.Extensible({
            "storage_class": "LocalStorage",
            "storage_options": figcan.Extensible({
                "path": "lfs-storage"
            }),
            "action_lifetime": 900,
        })
    }),
}

default_config = {
    "JWT_SECRET_KEY": None,
    "TRANSFER_ADAPTERS": figcan.Extensible(default_transfer_config),
    "TESTING": False,
    "AUTHENTICATORS": [
        'giftless.auth.allow_anon:read_only'
    ],
    "JWT": {
        'enabled': False,
        'options': figcan.Extensible({
            'secret_key': 'change-me',
            'key_id': 'giftless-internal-jwt-key'
        })
    }
}


def configure(app, additional_config: Optional[Dict] = None):
    """Configure a Flask app using Figcan managed configuration object
    """
    config = _compose_config(additional_config)
    app.config.update(config)
    return app


def _compose_config(additional_config: Optional[Dict] = None) -> figcan.Configuration:
    """Compose configuration object from all available sources
    """
    config = figcan.Configuration(default_config)
    if os.environ.get(f'{ENV_PREFIX}CONFIG_FILE'):
        with open(os.environ[f'{ENV_PREFIX}CONFIG_FILE']) as f:
            config_from_file = yaml.safe_load(f)
            config.apply(config_from_file)
        os.environ.pop(f'{ENV_PREFIX}CONFIG_FILE')
    if additional_config:
        config.apply(additional_config)
    config.apply_flat(os.environ, prefix=ENV_PREFIX)  # type: ignore
    return config
