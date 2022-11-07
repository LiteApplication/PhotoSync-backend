#!/bin/sh

# This is the path to a server state that will be used for reproducible testing.
SERVER_TEMPLATE="tests/server_env"
SERVER_WEBROOT="`pwd`/web"

# The template will be copied to this directory, and the server will be run from there.
SERVER_STATE="/tmp/photosync_server_test"

# Create a new server state from the template.
echo "Creating server state from template..."
mkdir -p $SERVER_STATE
rm -rf $SERVER_STATE
cp -r $SERVER_TEMPLATE $SERVER_STATE -v

export FLASK_APP=./server/main.py:app
export PIPENV_VERBOSITY=-1
export FLASK_DEBUG=1
export PHOTOSYNC_CONFIG=$SERVER_STATE/config.conf
export PHOTOSYNC_WEBROOT=$SERVER_WEBROOT
export PHOTOSYNC_TESTING=$SERVER_TEMPLATE

# Replace {SERVER_STATE} with the actual path in the config file.
sed -i "s|{SERVER_STATE}|$SERVER_STATE|g" $SERVER_STATE/config.conf
sed -i "s|{SERVER_WEBROOT}|$SERVER_WEBROOT|g" $SERVER_STATE/config.conf


echo "Starting server..."
pipenv run flask run --debugger -h 0.0.0.0 -p 2701
