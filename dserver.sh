#!/bin/sh
export FLASK_APP=./server/main.py:app
export PIPENV_VERBOSITY=-1
export FLASK_DEBUG=1
export PHOTOSYNC_CONFIG=config.conf

# Check if we are in a virtualenv
if [ -z "$VIRTUAL_ENV" ]; then
    python -m server.main --config $PHOTOSYNC_CONFIG
else
    pipenv run flask run --debugger -h 0.0.0.0 -p 8080
fi
