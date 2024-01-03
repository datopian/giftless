#!/bin/bash

# Determine the tag for Docker images based on GitHub Actions environment
# variables.

set -eo pipefail

if [ -n "$GITHUB_HEAD_REF" ]; then
    # For pull requests
    echo ${GITHUB_HEAD_REF} | sed -E 's,/,-,g'
else
    # For push events
    echo ${GITHUB_REF} | sed -E 's,refs/(heads|tags)/,,' | sed -E 's,/,-,g'
fi
