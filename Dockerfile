# Dockerfile for uWSGI wrapped Giftless Git LFS Server
# Shared build ARGs among stages
ARG WORKDIR=/app
ARG VENV="$WORKDIR/.venv"

### --- Build Depdendencies ---
FROM python:3.12 AS builder
ARG UWSGI_VERSION=2.0.23
# Common WSGI middleware modules to be pip-installed
# These are not required in every Giftless installation but are common enough
ARG EXTRA_PACKAGES="wsgi_cors_middleware"
# expose shared ARGs
ARG WORKDIR
ARG VENV

# Set WORKDIR (also creates the dir)
WORKDIR $WORKDIR

# Install packages to build wheels for uWSGI and other requirements
RUN set -eux ;\
    export DEBIAN_FRONTEND=noninteractive ;\
    apt-get update ;\
    apt-get install -y --no-install-recommends build-essential libpcre3 libpcre3-dev git ;\
    rm -rf /var/lib/apt/lists/*

# Create virtual env to store dependencies, "activate" it
RUN python -m venv --upgrade-deps "$VENV"
ENV VIRTUAL_ENV="$VENV" PATH="$VENV/bin:$PATH"

# Set a couple pip-related settings
# Wait a bit longer for slow connections
ENV PIP_TIMEOUT=100
# Don't nag about newer pip
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Don't cache pip packages
ENV PIP_NO_CACHE_DIR=1
# Require activated virtual environment
ENV PIP_REQUIRE_VIRTUALENV=1
# Eventual python cache files go here (not to be copied)
ENV PYTHONPYCACHEPREFIX=/tmp/__pycache__

# Install runtime dependencies
RUN --mount=target=/build-ctx \
    pip install -r /build-ctx/requirements/main.txt
RUN pip install uwsgi==$UWSGI_VERSION
# Install extra packages into the virtual env
RUN pip install ${EXTRA_PACKAGES}

# Copy project contents necessary for an editable install
COPY .git .git/
COPY giftless giftless/
COPY pyproject.toml .
# Editable-install the giftless package (add a kind of a project path reference in site-packages)
# To detect the package version dynamically, setuptools-scm needs the git binary
RUN pip install -e .

### --- Build Final Image ---
FROM python:3.12-slim AS final
LABEL org.opencontainers.image.authors="Shahar Evron <shahar.evron@datopian.com>"

ARG USER_NAME=giftless
# Writable path for local LFS storage
ARG STORAGE_DIR=/lfs-storage
# Set to true to add a runtime dockerhub deprecation warning
ARG IS_DOCKERHUB
# expose shared ARGs
ARG WORKDIR
ARG VENV

# Set WORKDIR (also creates the dir)
WORKDIR $WORKDIR

# Create a user and set local storage write permissions
RUN set -eux ;\
    useradd -d "$WORKDIR" "$USER_NAME" ;\
    mkdir "$STORAGE_DIR" ;\
    chown "$USER_NAME" "$STORAGE_DIR"

# Install runtime dependencies
RUN set -eux ;\
    export DEBIAN_FRONTEND=noninteractive ;\
    apt-get update ;\
    apt-get install -y libpcre3 libxml2 tini ;\
    rm -rf /var/lib/apt/lists/*

# Use the virtual env with dependencies from builder stage
COPY --from=builder "$VENV" "$VENV"
ENV VIRTUAL_ENV="$VENV" PATH="$VENV/bin:$PATH"
# Copy project source back into the same path referenced by the editable install
COPY --from=builder "$WORKDIR/giftless" "giftless"

# Copy desired docker-entrypoint
RUN --mount=target=/build-ctx set -eux ;\
    target_de=scripts/docker-entrypoint.sh ;\
    mkdir -p "$(dirname "$target_de")" ;\
    if [ "${IS_DOCKERHUB:-}" = true ]; then \
        cp /build-ctx/scripts/docker-entrypoint-dockerhub.sh "$target_de" ;\
    else \
        cp /build-ctx/scripts/docker-entrypoint.sh "$target_de" ;\
    fi

# Set runtime properties
USER $USER_NAME
ENV GIFTLESS_TRANSFER_ADAPTERS_basic_options_storage_options_path="$STORAGE_DIR"
ENV UWSGI_MODULE="giftless.wsgi_entrypoint"

ENTRYPOINT ["tini", "--", "scripts/docker-entrypoint.sh"]
CMD ["uwsgi", "-s", "127.0.0.1:5000", "-M", "-T", "--threads", "2", "-p", "2", \
     "--manage-script-name", "--callable", "app"]

# TODO remove this STOPSIGNAL override after uwsgi>=2.1
STOPSIGNAL SIGQUIT
