# Dockerfile for uWSGI wrapped Giftless Git LFS Server

FROM python:3.7-slim

EXPOSE 5000:5000

ARG UWSGI_VERSION=2.0.18
ENV UWSGI_MODULE "gitlfs.server.uwsgi_entrypoint"

# Install uWSGI
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y build-essential libpcre3 libpcre3-dev tini \
    && pip install -U pip \
    && pip install uwsgi==$UWSGI_VERSION \
    && apt-get remove -y --purge build-essential libpcre3-dev \
    && apt-get clean \
    && apt -y autoremove

# Install dependencies
RUN mkdir /app
COPY requirements.txt /app
RUN pip install -r /app/requirements.txt

# Copy project code
COPY . /app
RUN pip install -e /app

RUN useradd -d /app gitlfs
USER gitlfs
WORKDIR /app

ENTRYPOINT ["tini", "uwsgi", "--"]

CMD ["-s", "127.0.0.1:5000", "-M", "-T", "--threads", "2", "-p", "2", \
     "--manage-script-name", "--callable", "app"]
