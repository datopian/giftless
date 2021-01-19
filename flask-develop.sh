#!/bin/bash

export FLASK_ENV=development
export FLASK_APP=giftless.wsgi_entrypoint
export GIFTLESS_DEBUG=1

DEFAULT_CONFIG_FILE=giftless.yaml
if [ -z "$GIFTLESS_CONFIG_FILE" ]; then
    if [ -f "$DEFAULT_CONFIG_FILE" ]; then
        export GIFTLESS_CONFIG_FILE="$DEFAULT_CONFIG_FILE"
        echo "GIFTLESS_CONFIG_FILE not set, defaulting to local config file $DEFAULT_CONFIG_FILE" >&2
    else
        echo "GIFTLESS_CONFIG_FILE not set and $DEFAULT_CONFIG_FILE not found, running with default configuration" >&2
    fi
else
    echo "Using configuration file: $GIFTLESS_CONFIG_FILE" >&2
fi

flask run $@
