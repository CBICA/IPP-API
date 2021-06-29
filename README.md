# IPP API

## Overview

Simple HTTP server the IPP frontend interface uses to query the database. The (sqlite) database stores user accounts and experiments, and is hardcoded to be created in the project root.

When a user is created, their password is hashed using bcrypt to verify future login attempts, and the current login session is verified by a generating a random login token. Non-public endpoints (i.e. those that require you to be signed in) authenticate users by searching the database for the token sent to the user. As a user only has one token, logging into a new session will log them out of their old session. Login tokens expire after 24h.

When an experiment is received, the POSTed form is serialized into JSON and any uploaded files are saved with a secure filename.

| Endpoint | Description | Public |
| -------- | ------- | ---------- |
| /users/new         | create user | Yes
| /users/auth        | authenticate user | Yes
| /experiments       | list user experiments | No
| /experiments/new   | create new experiment | No

## Installation

### Docker
(preferred method)
```sh
docker run -p 3330:5000 --name ipp-api --rm -it -v $PWD:/opt terf/ipp-api
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
