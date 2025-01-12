# Dockerfile for uWSGI wrapped Giftless Git LFS Server
# Shared build ARGs among stages
ARG WORKDIR=/app
ARG VENV="$WORKDIR/.venv"
ARG UV_VERSION=0.5.16

### Distroless uv version layer to be copied from (because COPY --from does not interpolate variables)
FROM ghcr.io/astral-sh/uv:$UV_VERSION AS uv

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

# Install uv to replace pip & friends
COPY --from=uv /uv /uvx /bin/

# Set a couple uv-related settings
# Wait a bit longer for slow connections
ENV UV_HTTP_TIMEOUT=100
# Don't cache packages
ENV UV_NO_CACHE=1

# Create virtual env to store dependencies, "activate" it
RUN uv venv "$VENV"
ENV VIRTUAL_ENV="$VENV" PATH="$VENV/bin:$PATH"

# Install runtime dependencies
RUN --mount=target=/build-ctx \
    uv pip install -r /build-ctx/requirements/main.txt
RUN uv pip install uwsgi==$UWSGI_VERSION
# Install extra packages into the virtual env
RUN uv pip install ${EXTRA_PACKAGES}

# Copy project contents necessary for an editable install
COPY .git .git/
COPY giftless giftless/
COPY pyproject.toml .
# Editable-install the giftless package (add a kind of a project path reference in site-packages)
# To detect the package version dynamically, setuptools-scm needs the git binary
RUN uv pip install -e .

### --- Build Final Image ---
FROM python:3.12-slim AS final
LABEL org.opencontainers.image.authors="Shahar Evron <shahar.evron@datopian.com>"

ARG USER_NAME=giftless
# Writable path for local LFS storage
ARG STORAGE_DIR=/lfs-storage
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

# Set runtime properties
USER $USER_NAME
ENV GIFTLESS_TRANSFER_ADAPTERS_basic_options_storage_options_path="$STORAGE_DIR"
ENV UWSGI_MODULE="giftless.wsgi_entrypoint"

ENTRYPOINT ["tini", "--", "uwsgi"]
CMD ["-s", "127.0.0.1:5000", "-M", "-T", "--threads", "2", "-p", "2", \
     "--manage-script-name", "--callable", "app"]

# TODO remove this STOPSIGNAL override after uwsgi>=2.1
STOPSIGNAL SIGQUIT
