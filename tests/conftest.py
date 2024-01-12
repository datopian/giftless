import pathlib
import shutil
from typing import Generator, cast

import flask
import pytest
from flask.ctx import AppContext
from flask.testing import FlaskClient

from giftless.app import init_app
from giftless.auth import allow_anon, authentication


@pytest.fixture
def storage_path(tmp_path: pathlib.Path) -> Generator:
    path = tmp_path / "lfs-tests"
    path.mkdir()
    try:
        yield str(tmp_path)
    finally:
        shutil.rmtree(path)


@pytest.fixture
def app(storage_path: str) -> flask.Flask:
    """Session fixture to configure the Flask app"""
    app = init_app(
        additional_config={
            "TESTING": True,
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
def authz_full_access(
    app_context: AppContext,
) -> (
    Generator
):  # needed to ensure we call init_authenticators before app context is destroyed
    """Fixture that enables full anonymous access to all actions for tests that
    use it
    """
    try:
        authentication.push_authenticator(
            allow_anon.read_write  # type:ignore[arg-type]
        )
        yield
    finally:
        authentication.init_authenticators(reload=True)
