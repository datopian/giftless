#!/bin/bash

export FLASK_ENV=development
export FLASK_APP=giftless.wsgi_entrypoint
export GIFTLESS_DEBUG=1

flask run $@
