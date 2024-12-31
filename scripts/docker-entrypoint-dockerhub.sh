#!/bin/sh
# Deprecation warning for images on dockerhub.

# ANSI color codes
RED='\033[1;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

echo "${RED}**********************************************${RESET}"
echo "${YELLOW}WARNING:${RESET} This Docker image from docker.io is deprecated!"
echo "${YELLOW}It will no longer be maintained. Please use ghcr.io/datopian/giftless."
echo "${YELLOW}Refer to https://github.com/datopian/giftless for more details."
echo "${RED}**********************************************${RESET}"

exec "$@"
