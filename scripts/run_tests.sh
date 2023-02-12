#!/usr/bin/env bash

export PYTHONIOENCODING=utf-8

mypy src --no-incremental
flake8 src
pytest -svv -x

