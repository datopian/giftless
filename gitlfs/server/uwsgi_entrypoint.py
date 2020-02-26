"""Entry point module for uWSGI

This is used when running the app using uWSGI. You do not need to use it if running
through some other WSGI or other server, or for local development.
"""

from .app import init_app

app = init_app()
