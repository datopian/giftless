# Makefile for giftless
PACKAGE_NAME := giftless
PACKAGE_DIRS := giftless
TESTS_DIR := tests

SHELL := bash
PYTHON := python
PIP := pip
PIP_COMPILE := pip-compile
PYTEST := pytest
DOCKER := docker
GIT := git

DOCKER_HOST := docker.io
DOCKER_REPO := datopian
DOCKER_IMAGE_NAME := giftless
DOCKER_IMAGE_TAG := latest
DOCKER_CACHE_FROM := docker.io/datopian/giftless:latest

PYTEST_EXTRA_ARGS :=

SOURCE_FILES := $(shell find $(PACKAGE_DIRS) $(TESTS_DIR) -type f -name "*.py")
SENTINELS := .make-cache
DIST_DIR := dist

PYVER := $(shell $(PYTHON) -c "import sys;print(f'{sys.version_info[0]}{sys.version_info[1]}')")
VERSION := $(shell $(PYTHON) -c "from importlib.metadata import version;print(version('$(PACKAGE_NAME)'))")

default: help

## Regenerate requirements files
requirements: requirements/dev.txt requirements/dev.in requirements/main.txt requirements/main.in

## Set up the development environment
dev-setup: $(SENTINELS)/dev-setup

## Run all tests
test: $(SENTINELS)/dev-setup
	$(PYTEST) $(PYTEST_EXTRA_ARGS) $(PACKAGE_DIRS) $(TESTS_DIR)

## Build a local Docker image
docker: requirements.txt
	$(DOCKER) build --cache-from "$(DOCKER_CACHE_FROM)" -t $(DOCKER_HOST)/$(DOCKER_REPO)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) .

## Tag and push a release
release:
	@echo
	@echo "Package $(PACKAGE_NAME) releases are managed via GitHub"

## Clean all generated files
distclean:
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	rm -rf $(SENTINELS)/dist

## Create distribution files to upload to pypi
dist: $(SENTINELS)/dist

## Build project documentation HTML files
docs-html:
	@cd docs && $(MAKE) html

.PHONY: test docker release dist distclean requirements docs-html

requirements/main.txt: requirements/main.in
	$(PIP_COMPILE) --no-emit-index-url -o requirements/main.txt requirements/main.in

requirements/dev.txt: requirements/dev.in requirements/main.txt
	$(PIP_COMPILE) --no-emit-index-url -o requirements/dev.txt requirements/dev.in

$(DIST_DIR)/$(PACKAGE_NAME)-$(VERSION).tar.gz $(DIST_DIR)/$(PACKAGE_NAME)-$(VERSION)-py3-none-any.whl: $(SOURCE_FILES) VERSION README.md | $(SENTINELS)/dist-setup
	$(PYTHON) -m build

$(SENTINELS):
	mkdir $@

$(SENTINELS)/dist-setup: | $(SENTINELS)
	$(PIP) install -U pip wheel twine pre-commit
	@touch $@

$(SENTINELS)/dist: $(SENTINELS)/dist-setup $(DIST_DIR)/$(PACKAGE_NAME)-$(VERSION).tar.gz $(DIST_DIR)/$(PACKAGE_NAME)-$(VERSION)-py3-none-any.whl | $(SENTINELS)
	@touch $@

$(SENTINELS)/dev-setup: requirements.txt dev-requirements.txt | $(SENTINELS)
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	$(PIP) install -r dev-requirements.txt
	@touch $@

# Help related variables and targets

GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
RESET  := $(shell tput -Txterm sgr0)
TARGET_MAX_CHAR_NUM := 20

## Show help
help:
	@echo ''
	@echo 'Usage:'
	@echo '  ${YELLOW}make${RESET} ${GREEN}<target>${RESET}'
	@echo ''
	@echo 'Targets:'
	@awk '/^[a-zA-Z\-\_0-9]+:/ { \
	  helpMessage = match(lastLine, /^## (.*)/); \
	  if (helpMessage) { \
	    helpCommand = substr($$1, 0, index($$1, ":")-1); \
	    helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
	    printf "  ${YELLOW}%-$(TARGET_MAX_CHAR_NUM)s${RESET} ${GREEN}%s${RESET}\n", helpCommand, helpMessage; \
	  } \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)
