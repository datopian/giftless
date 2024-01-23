Developer Guide
===============
`giftless` is based on Flask, with the following additional libraries:

* [Flask Classful](http://flask-classful.teracy.org/) for simplifying API
endpoint implementation with Flask
* [Marshmallow](https://marshmallow.readthedocs.io/en/stable/) for
input / output serialization and validation
* [figcan](https://github.com/shoppimon/figcan) for configuration handling

You must have Python 3.10 or newer set up to run or develop `giftless`.

## Code Style
We use the following tools and standards to write `giftless` code:
* `flake8` to check your Python code for PEP8 compliance
* `import` statements are checked by `isort` and should be organized
accordingly
* Type checking is done using `mypy`

Maximum line length is set to 120 characters.

## Setting up a Virtual Environment
You should develop `giftless` in a virtual environment. We use [`pip-tools`][1]
to manage both development and runtime dependencies.

The following snippet is an example of how to set up your virtual environment
for development:

    $ python3 -m venv .venv
    $ . .venv/bin/activate

    (.venv) $ pip install -r dev-requirements.txt
    (.venv) $ pip-sync dev-requirements.txt requirements.txt

## Running the tests
Once in a virtual environment, you can simply run `make test` to run all tests
and code style checks:

    $ make test

We use `pytest` for Python unit testing.

In addition, simple functions can specify some `doctest` style tests in the
function docstring. These tests will be tested automatically when unit tests
are executed.

## Building a Docker image
Simply run `make docker` to build a `uWSGI` wrapped Docker image for Giftless.
The image will be named `datopian/giftless:latest` by default. You can change
it, for example:

    $ make docker DOCKER_REPO=mycompany DOCKER_IMAGE_TAG=1.2.3

Will build a Docekr image tagged `mycompany/giftless:1.2.3`.

[1]: [Pip Tools](https://github.com/jazzband/pip-tools)
