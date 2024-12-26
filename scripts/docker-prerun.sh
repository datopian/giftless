#!/bin/sh

# ANSI color codes
RED='\033[1;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

if [ "$IS_DOCKERHUB" = true ]; then
    echo "${RED}**********************************************${RESET}"
    echo "${YELLOW}WARNING:${RESET} This Docker image from docker.io is deprecated!"
    echo "${YELLOW}It will no longer be maintained. Please use ghcr.io/datopian/giftless."
    echo "${YELLOW}Refer to https://github.com/datopian/giftless for more details."
    echo "${RED}**********************************************${RESET}"
fi

exec "$@"
