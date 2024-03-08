"""Fixtures for giftless testing."""
import pathlib
import shutil
from collections.abc import Generator
from typing import Any

import flask
import pytest
from flask.ctx import AppContext
from flask.testing import FlaskClient

from giftless.app import init_app
from giftless.auth import allow_anon, authentication
from tests.helpers import legacy_endpoints_id


@pytest.fixture
def storage_path(tmp_path: pathlib.Path) -> Generator:
    path = tmp_path / "lfs-tests"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path)


@pytest.fixture(params=[False], ids=legacy_endpoints_id)
def app(storage_path: str, request: Any) -> flask.Flask:
    """Session fixture to configure the Flask app."""
    legacy_endpoints = request.param
    app = init_app(
        additional_config={
            "TESTING": True,
            "LEGACY_ENDPOINTS": legacy_endpoints,
            "TRANSFER_ADAPTERS": {
                "basic": {
                    "options": {"storage_options": {"path": storage_path}}
                }
            },
        }
    )
    app.config.update({"SERVER_NAME": "giftless.local"})
    return app


@pytest.fixture
def app_context(app: flask.Flask) -> Generator:
    ctx = app.app_context()
    try:
        ctx.push()
        yield ctx
    finally:
        ctx.pop()


@pytest.fixture
def test_client(app_context: AppContext) -> FlaskClient:
    test_client: FlaskClient = app_context.app.test_client()
    return test_client


@pytest.fixture
def _authz_full_access(
    app_context: AppContext,
) -> Generator:
    """Fixture that enables full anonymous access to all actions for
    tests that use it.  Try block needed to ensure we call
    init_authenticators before app context is destroyed.
    """
    try:
        authentication.push_authenticator(
            allow_anon.read_write  # type:ignore[arg-type]
        )
        yield
    finally:
        authentication.init_authenticators(reload=True)
