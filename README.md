Giftless - a Pluggable Git LFS Server
=====================================
Giftless a Python implementation of a [Git LFS](1) Server. It is designed 
with flexibility in mind, to allow pluggable storage backends, transfer 
methods and authentication methods. 

Installation & Quick Start
--------------------------

### Running using Docker
TBD

### Installing & Running from Source
TBD

### Configuration
TBD

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
