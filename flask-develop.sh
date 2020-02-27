#!/bin/bash

export FLASK_ENV=development
export FLASK_APP=gitlfs.server.wsgi_entrypoint

flask run
