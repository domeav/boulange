#!/bin/bash

# run this before committing

poetry run isort boulange resto
poetry run black boulange resto
poetry run flake8 --max-line-length 200 boulange resto
