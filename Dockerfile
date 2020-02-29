# Dockerfile for uWSGI wrapped Giftless Git LFS Server

### --- Build Depdendencies ---

FROM python:3.7 as builder
MAINTAINER "Shahar Evron <shahar.evron@datopian.com>"

# Build wheels for uWSGI and all requirements
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y build-essential libpcre3 libpcre3-dev git
RUN pip install -U pip
RUN mkdir /wheels

ARG UWSGI_VERSION=2.0.18
RUN pip wheel -w /wheels uwsgi==$UWSGI_VERSION

COPY requirements.txt /
RUN pip wheel -w /wheels -r /requirements.txt

### --- Build Final Image ---

FROM python:3.7-slim

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y libpcre3 libxml2 tini \
    && apt-get clean \
    && apt -y autoremove

RUN mkdir /app

# Install dependencies
COPY --from=builder /wheels /wheels
RUN pip install /wheels/*.whl

# Copy project code
COPY . /app
RUN pip install -e /app

ARG USER_NAME=giftless
ARG STORAGE_DIR=/lfs-storage
ENV GIFTLESS_TRANSFER_ADAPTERS_basic_options_storage_options_path $STORAGE_DIR

RUN useradd -d /app $USER_NAME
RUN mkdir $STORAGE_DIR
RUN chown $USER_NAME $STORAGE_DIR

USER $USER_NAME

WORKDIR /app

ENV UWSGI_MODULE "giftless.wsgi_entrypoint"

EXPOSE 5000:5000

ENTRYPOINT ["tini", "uwsgi", "--"]

CMD ["-s", "127.0.0.1:5000", "-M", "-T", "--threads", "2", "-p", "2", \
     "--manage-script-name", "--callable", "app"]
