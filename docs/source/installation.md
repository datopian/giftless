Installation / Deployment
=========================

You can install and run Giftless in different ways, depending on your needs:

## Running from Docker image
Giftless is available as a Docker image available from
[Docker Hub](https://hub.docker.com/r/datopian/giftless)

To run the latest version of Giftless in HTTP mode, listening
on port 8080, run:

```
$ docker run --rm -p 8080:8080 datopian/giftless \
    -M -T --threads 2 -p 2 --manage-script-name --callable app \
    --http 0.0.0.0:8080
```

This will pull the image and run it.

Alternatively, to run in `WSGI` mode you can run:

```
$ docker run --rm -p 5000:5000 datopian/giftless
```

This will require an HTTP server such as *nginx* to proxy HTTP requests to it.

If you need to, you can also build the Docker image locally as described below.

## Running from Pypi package
You can install Giftless into your Python environment of choice (3.7+) using pip.
It is recommended to install Giftless into a virtual environment:

```shell
(venv) $ pip install uwsgi
(venv) $ pip install giftless
```

Once installed, you can run Giftless locally with uWSGI:

```
# Run uWSGI (see uWSGI's manual for help on all arguments)
(venv) $ uwsgi -M -T --threads 2 -p 2 --manage-script-name \
    --module giftless.wsgi_entrypoint --callable app --http 127.0.0.1:8080
```

This will listen on port `8080`.

You should be able to replace `uwsgi` with any other WSGI server, such as `gunicorn`.

## Running from source installation
You can install and run `giftless` from source:

```shell
$ git clone https://github.com/datopian/giftless.git

# Initialize a virtual environment
$ cd giftless
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt
```

You can then proceed to run Giftless with a WSGI server as
described above.

Note that for non-production use you may avoid using a WSGI server and rely
on Flask's built in development server. This should **never** be done in a
production environment:

```shell
(venv) $ ./flask-develop.sh
```

In development mode, Giftless will be listening on `http://127.0.0.1:5000`
