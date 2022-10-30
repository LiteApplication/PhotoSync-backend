#!/bin/sh
export FLASK_APP=./server/main.py:app
export PIPENV_VERBOSITY=-1
export FLASK_DEBUG=1
pipenv run flask run --debugger -h 0.0.0.0 -p 8080
