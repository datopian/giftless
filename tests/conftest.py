import shutil

import pytest
from flask.ctx import AppContext

from giftless.app import init_app


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
