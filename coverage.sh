#!/bin/sh
pytest --cov=custom_components/lg_tv_serial tests/ --cov-report term-missing --cov-report html
mypy custom_components  --check-untyped-defs
