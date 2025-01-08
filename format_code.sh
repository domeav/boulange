#!/bin/bash

# run this before committing

poetry run isort boulange resto
poetry run black -l 88 boulange resto
poetry run flake8 --max-line-length 150 boulange resto
