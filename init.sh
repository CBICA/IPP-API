#!/bin/bash

export FLASK_APP=/opt
export FLASK_ENV=development
export UPLOAD_FOLDER=/var/uploads
export PYTHONPATH="${FLASK_APP}:${PYTHONPATH}"
mkdir -p $UPLOAD_FOLDER
/usr/sbin/sshd -o ListenAddress=0.0.0.0 -p 22
flask run --host=0.0.0.0 "$@"
