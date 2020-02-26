# Makefile for py-git-lfs-server

PACKAGE_DIRS := gitlfs
TESTS_DIR := tests

SHELL := bash
PIP := pip
PIP_COMPILE := pip-compile
PYTEST := pytest
DOCKER := docker


requirements.txt: requirements.in
	$(PIP_COMPILE) --no-index --output-file=requirements.txt requirements.in

dev-requirements.txt: dev-requirements.in
	$(PIP_COMPILE) --no-index --output-file=dev-requirements.txt dev-requirements.in

test: dev-requirements.txt
	$(PIP) install -r dev-requirements.txt -e .
	$(PYTEST) $(PACKAGE_DIRS) $(TESTS_DIR)

.PHONY: test
