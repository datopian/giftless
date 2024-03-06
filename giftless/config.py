"""Configuration handling helper functions and default configuration."""
import os
import warnings
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from figcan import Configuration, Extensible  # type:ignore[attr-defined]
from flask import Flask

ENV_PREFIX = "GIFTLESS_"
ENV_FILE = ".env"

default_transfer_config = {
    "basic": Extensible(
        {
            "factory": "giftless.transfer.basic_streaming:factory",
            "options": Extensible(
                {
                    "storage_class": (
                        "giftless.storage.local_storage:LocalStorage"
                    ),
                    "storage_options": Extensible({"path": "lfs-storage"}),
                    "action_lifetime": 900,
                }
            ),
        }
    ),
}

default_config = {
    "TESTING": False,
    "DEBUG": False,
    "LEGACY_ENDPOINTS": True,
    "TRANSFER_ADAPTERS": Extensible(default_transfer_config),
    "AUTH_PROVIDERS": ["giftless.auth.allow_anon:read_only"],
    "PRE_AUTHORIZED_ACTION_PROVIDER": {
        "factory": "giftless.auth.jwt:factory",
        "options": {
            "algorithm": "HS256",
            "private_key": "change-me",
            "private_key_file": None,
            "public_key": None,
            "public_key_file": None,
            "default_lifetime": 60,  # 60 seconds for default actions
            "key_id": "giftless-internal-jwt-key",
        },
    },
    "MIDDLEWARE": [],
}

load_dotenv()


def configure(app: Flask, additional_config: dict | None = None) -> Flask:
    """Configure a Flask app using Figcan managed configuration object."""
    config = _compose_config(additional_config)
    app.config.update(config)
    if app.config["LEGACY_ENDPOINTS"]:
        warnings.warn(
            FutureWarning(
                "LEGACY_ENDPOINTS (starting with '<org>/<repo>/') are enabled"
                " as the default. They will be eventually removed in favor of"
                " those starting with '<org-path>/<repo>.git/info/lfs/')."
                " Switch your clients to them and set the configuration"
                " option to False to disable this warning."
            ),
            stacklevel=1,
        )
    return app


def _compose_config(
    additional_config: dict[str, Any] | None = None,
) -> Configuration:
    """Compose configuration object from all available sources."""
    config = Configuration(default_config)
    environ = dict(
        os.environ
    )  # Copy the environment as we're going to change it

    if environ.get(f"{ENV_PREFIX}CONFIG_FILE"):
        with Path(environ[f"{ENV_PREFIX}CONFIG_FILE"]).open() as f:
            config_from_file = yaml.safe_load(f)
        config.apply(config_from_file)
        environ.pop(f"{ENV_PREFIX}CONFIG_FILE")

    if environ.get(f"{ENV_PREFIX}CONFIG_STR"):
        config_from_file = yaml.safe_load(environ[f"{ENV_PREFIX}CONFIG_STR"])
        config.apply(config_from_file)
        environ.pop(f"{ENV_PREFIX}CONFIG_STR")

    config.apply_flat(environ, prefix=ENV_PREFIX)

    if additional_config:
        config.apply(additional_config)

    return config
