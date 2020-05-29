Giftless - a Pluggable Git LFS Server
=====================================

[![Build Status](https://travis-ci.org/datopian/giftless.svg?branch=master)](https://travis-ci.org/datopian/giftless)
[![Maintainability](https://api.codeclimate.com/v1/badges/58f05c5b5842c8bbbdbb/maintainability)](https://codeclimate.com/github/datopian/giftless/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/58f05c5b5842c8bbbdbb/test_coverage)](https://codeclimate.com/github/datopian/giftless/test_coverage)

Giftless a Python implementation of a [Git LFS](1) Server. It is designed
with flexibility in mind, to allow pluggable storage backends, transfer
methods and authentication methods.

Giftless supports the *basic* Git LFS transfer mode with the following
storage backends:
* Local storage
* [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/)
  with direct-to-cloud or streamed transfers

Additional transfer modes and storage backends could easily be added and
configured.

Installation & Quick Start
--------------------------

### Running using Docker
Giftless is available as a Docker image. You can simply use:

    $ docker run --rm -p 5000:5000 datopian/giftless

To pull and run Giftless on a system that supports Docker.

This will run the server in WSGI mode, which will require an HTTP server
such as *nginx* to proxy HTTP requests to it.

Alternatively, you can specify the following command line arguments to
have uWSGI run in HTTP mode, if no complex HTTP setup is required:

    $ docker run --rm -p 8080:8080 datopian/giftless \
        -M -T --threads 2 -p 2 --manage-script-name --callable app \
        --http 0.0.0.0:8080


If you need to, you can also build the Docker image locally as
described below.

### Installing & Running from Pypi
You can install Giftless into your Python environment of choice
(3.7+) using pip:

    (venv) $ pip install giftless

To run it, you most likely are going to need a WSGI server
installed such as uWSGI or Gunicorn. Here is an example of
how to run Giftless locally with uWSGI:

    # Install uWSGI or any other WSGI server
    $ (.venv) pip install uwsgi

    # Run uWSGI (see uWSGI's manual for help on all arguments)
    $ (.venv)  uwsgi -M -T --threads 2 -p 2 --manage-script-name \
        --module giftless.wsgi_entrypoint --callable app --http 127.0.0.1:8080

### Installing & Running from Source
You can install and run `giftless` from source:

    $ git clone https://github.com/datopian/giftless.git

    # Initialize a virtual environment
    $ cd giftless
    $ python3 -m venv .venv
    $ . .venv/bin/activate
    $ (.venv) pip install -r requirements.txt

You can then proceed to run Giftless with a WSGI server as
described above.

Note that for non-production use you may avoid using a WSGI server and rely
on Flask's built in development server. This should **never** be done in a
production environment:

    $ (.venv) ./flask-develop.sh

The default generated endpoint is <http://127.0.0.1:5000/>. Note: If you access
this endpoint, you should receive an error message (invalid route).


### Running a local example

1. Create a new project on Github or any other platform.
Here, we create a project named `example-proj-datahub-io`.

2. Add any data file to it.
The goal is to track this possible large file with
git-lfs and use Giftless as the local server. In our example,
we create a CSV named `research_data_factors.csv`.


3. Create a file named `giftless.yaml` in your project root directory with the
following content in order to have a local server:

```yaml
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: LocalStorage
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write
```

4. Export it:

```bash
$ export GIFTLESS_CONFIG_FILE=giftless.yaml
```


5. Start the Giftless server (by docker or Python).


6. Initialzie your git repo and connect it with the
remote project:

```bash
git init
git remote add origin YOUR_REMOTE_REPO
```

7. Track files with git-lfs:

```bash
git lfs track 'research_data_factors.csv'
git lfs track
git add .gitattributes #you should have a .gitattributes file at this point
git add "research_data_factors.csv"
git commit -m "Tracking data files"
```
  * You can see a list of tracked files with `git lfs ls-files`

8. Configure `lfs.url` to point to your local Giftless server instance:

```bash
git config -f .lfsconfig lfs.url http://127.0.0.1:5000/<user_or_org>/<repo>/
# in our case, we used http://127.0.0.1:5000/datopian/example-proj-datahub-io/;
# make sure to end your lfs.url with /
```

9. The previous configuration will produce changes into `.lfsconfig` file.
Add it to git:

```bash
git add .lfsconfig
git commit -m "New git-lfs server endpoint"
# if you don't see any changes, run git rm --cached *.csv and then re-add your files, then commit it
git lfs push origin master
```

### Configuration

It is also possible to configure Giftless' YAML file to use an external storage.

#### Azure Support

Modify your `giftless.yaml` file according to the following config:

```bash
    $ cat giftless.yaml

    TRANSFER_ADAPTERS:
      basic:
        factory: giftless.transfer.basic_external:factory
        options:
          storage_class: ..storage.azure:AzureBlobsStorage
          storage_options:
            connection_string: GetYourAzureConnectionStringAndPutItHere==
            container_name: lfs-storage
            path_prefix: large-files
```

#### Google Cloud Platform Support

Make sure to obtain your `credentials.json` file. More information 
[here](https://console.cloud.google.com/apis/credentials/serviceaccountkey).
You can export it directly with 

```bash
export GOOGLE_APPLICATION_CREDENTIALS="PATH_TO/credentials.json"
```

Make sure to also specify the path into the YAML file:

```bash
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: ..storage.google_cloud:GoogleCloudBlobStorage
      storage_options:
        bucket_name: datahub-bbb
        api_key: myAPI-key
        account_json_path: PATH_TO/credentials.json
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write
```

`api-key` and `account_json_path` are optional parameters.

After configuring your `giftless.yaml` file, export it:

```bash
$ export GIFTLESS_CONFIG_FILE=giftless.yaml
```

You will need uWSGI running. Install it with your prefereed package manager.
Here is an example of how to run it:
    
```bash
    # Run uWSGI in HTTP mode on port 8080
    $ uwsgi -M -T --threads 2 -p 2 --manage-script-name \
        --module giftless.wsgi_entrypoint --callable app --http 127.0.0.1:8080
```

See `giftless/config.py` for some default configuration options.

#### Transfer Adapters

TBD

#### Authenticators

TBD

#### Pre-Authorized Action Authenticators

TBD

#### Using Arbitrary WSGI Middleware

TBD

##### Fixing Generated URLs when Running Behind a Proxy

You can use the `ProxyFix` Werkzeug middleware to fix issues caused when
Giftless runs behind a reverse proxy, causing generated URLs to not match
the URLs expected by clients:

```yaml
MIDDLEWARE:
  - class: werkzeug.middleware.proxy_fix:ProxyFix
    kwargs:
      x_host: 1
      x_port: 1
      x_prefix: 1
```

##### Adding CORS Support

TBD


## Overview of the Giftless workflow

![mermaid-diagram-git-lfs-20200528](https://user-images.githubusercontent.com/32682903/83167859-43d99580-a0d6-11ea-8304-cb67f025adbf.png)

Development
-----------
`giftless` is based on Flask, with the following additional libraries:

* [Flask Classful](http://flask-classful.teracy.org/) for simplifying API
endpoint implementation with Flask
* [Marshmallow](https://marshmallow.readthedocs.io/en/stable/) for
input / output serialization and validation
* [flask-jwt-simple](https://flask-jwt-simple.readthedocs.io/en/latest/) for
handling JWT tokens
* [figcan](https://github.com/shoppimon/figcan) for configuration handling

You must have Python 3.7 and newer set up to run or develop `giftless`.

### Code Style
We use the following tools and standards to write `giftless` code:
* `flake8` to check your Python code for PEP8 compliance
* `import` statements are checked by `isort` and should be  organized
accordingly
* Type checking is done using `mypy`

Maximum line length is set to 120 characters.

### Setting up a Virtual Environment
You should develop `giftless` in a virtual environment. We use [`pip-tools`](2)
to manage both development and runtime dependencies.

The following snippet is an example of how to set up your virtual environment
for development:

    $ python3 -m venv .venv
    $ . .venv/bin/activate

    (.venv) $ pip install -r dev-requirements.txt
    (.venv) $ pip-sync dev-requirements.txt requirements.txt

### Running tests
Once in a virtual environment, you can simply run `make test` to run all tests
and code style checks:

    $ make test

We use `pytest` for Python unit testsing.

In addition, simple functions can specify some `doctest` style tests in the
function docstring. These tests will be tested automatically when unit tests
are executed.

### Building a Docker image
Simply run `make docker` to build a `uWSGI` wrapped Docker image for `giftless`.
The image will be named `datopian/giftless:latest` by default. You can change
it, for example:

    $ make docker DOCKER_REPO=mycompany DOCKER_IMAGE_TAG=1.2.3

Will build a Docekr image tagged `mycompany/giftless:1.2.3`.

License
-------
Copyright (C) 2020, Viderum, Inc.

Giftless is free / open source software and is distributed under the terms of
the MIT license. See [LICENSE](LICENSE) for details.


 [1]: https://git-lfs.github.com/
