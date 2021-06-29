#!/bin/bash

export FLASK_APP=/opt
export FLASK_ENV=development
export UPLOAD_FOLDER=/var/uploads
mkdir -p $UPLOAD_FOLDER
flask run --host=0.0.0.0 "$@"
