import pytest
from flask.ctx import AppContext

from gitlfs.server.app import init_app


@pytest.fixture(scope='session')
def app():
    """Session fixture to configure the Flask app
    """
    app = init_app()
    app.config['TESTING'] = True
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
def test_client(context: AppContext):
    test_client = context.app.test_client()
    return test_client
