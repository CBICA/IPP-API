# IPP API

## Overview

Simple HTTP server the IPP frontend interface uses to query the (sqlite) database, which stores user accounts and experiments.

| Endpoint | Description | Public |
| -------- | ------- | ---------- |
| /users/new         | create user | Yes
| /users/auth        | authenticate user | Yes
| /experiments       | list user experiments | No
| /experiments/new   | create new experiment | No

### Workflow
1. User creates account (/users/new), or logins (/users/auth)
2. User creates experiment by submitting form (/experiments/new). Uploaded files and the form, serialized as JSON, are placed in a folder like `UPLOAD_FOLDER/uid/submitted/eid` where UPLOAD_FOLDER is an environment variable, uid is a users ID, and eid is an experiment ID. In addition to the "submitted" namespace (meant for the backend to queue) there's an "editing" (ignored by backend) and "completed" namespace. The location of an experiments files determines the status.
3. IPP backend runs job, places output in `UPLOAD_FOLDER/uid/completed/eid`

When a user is created, their password is hashed using bcrypt, and they are given a login token. Non-public endpoints (i.e. those that require you to be signed in) authenticate users by searching the database for the token sent to the user. As a user only has one token, logging into a new session will log them out of their old session. Login tokens expire after 24h.

## Installation

### Docker
(preferred method)
```sh
./run.sh
```
### Manual (PIP)
Officially, flask supports python >= 3.6, but seems to work fine with python >= 3.4.
```sh
git clone https://github.com/CBICA/IPP-API.git
cd ipp-API
pip install -r requirements.txt
export FLASK_APP=$PWD
export FLASK_ENV=development
export UPLOAD_FOLDER=/var/uploads
mkdir -p $UPLOAD_FOLDER
forever start -c flask run --host=0.0.0.0 --port 5000
```
`forever` is a more robust alternative to `nohup` + backgrounding process.
Either terminate SSL at load balancer or provide `--cert` / `--key` for HTTPS.

## Todo
- rate limiting endpoints (in application or with fail2ban?)
- user accounts need to be approved?
- reset password / other functionality that requires mail server
