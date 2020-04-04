import shutil

import pytest
from flask.ctx import AppContext

from giftless.app import init_app
from giftless.auth import allow_anon, authentication


@pytest.fixture()
def storage_path(tmp_path):
    path = tmp_path / "lfs-tests"
    path.mkdir()
    try:
        yield str(tmp_path)
    finally:
        shutil.rmtree(path)


@pytest.fixture()
def app(storage_path):
    """Session fixture to configure the Flask app
    """
    app = init_app(additional_config={
        "TESTING": True,
        "TRANSFER_ADAPTERS": {
            "basic": {
                "options": {
                    "storage_options": {
                        "path": storage_path
                    }
                }
            }
        }
    })
    app.config.update({"SERVER_NAME": 'giftless.local'})
    return app


@pytest.fixture()
def app_context(app):
    ctx = app.app_context()
    try:
        ctx.push()
        yield ctx
    finally:
        ctx.pop()


@pytest.fixture()
def test_client(app_context: AppContext):
    test_client = app_context.app.test_client()
    return test_client


@pytest.fixture()
def authz_full_access(app_context):  # needed to ensure we call init_authenticators before app context is destroyed
    """Fixture that enables full anonymous access to all actions for tests that
    use it
    """
    try:
        authentication.push_authenticator(allow_anon.read_write)
        yield
    finally:
        authentication.init_authenticators(reload=True)
