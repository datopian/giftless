#!/bin/bash

export FLASK_ENV=development
export FLASK_APP=giftless.wsgi_entrypoint
export GIFTLESS_DEBUG=1

export GIFTLESS_CONFIG_FILE=${GIFTLESS_CONFIG_FILE:-giftless.yaml}
echo "Using configuration file: $GIFTLESS_CONFIG_FILE"

flask run $@
