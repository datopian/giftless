# Makefile for giftless

PACKAGE_DIRS := giftless
TESTS_DIR := tests

SHELL := bash
PIP := pip
PIP_COMPILE := pip-compile
PYTEST := pytest
DOCKER := docker

DOCKER_REPO := datopian
DOCKER_IMAGE_NAME := giftless
DOCKER_IMAGE_TAG := latest
DOCKER_CACHE_FROM := datopian/giftless:latest


requirements.txt: requirements.in
	$(PIP_COMPILE) --no-index --output-file=requirements.txt requirements.in

dev-requirements.txt: dev-requirements.in
	$(PIP_COMPILE) --no-index --output-file=dev-requirements.txt dev-requirements.in

test: dev-requirements.txt
	$(PIP) install -r dev-requirements.txt -e .
	$(PYTEST) $(PACKAGE_DIRS) $(TESTS_DIR)

docker: requirements.txt
	$(DOCKER) build --cache-from "$(DOCKER_CACHE_FROM)" -t $(DOCKER_REPO)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) .

.PHONY: test
