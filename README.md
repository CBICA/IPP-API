# IPP API

## Overview

Simple HTTP server the IPP frontend interface uses to query the (sqlite) database, which stores user accounts and experiments.


| Endpoint | Description | Authenticated | Public |
| -------- | ----------- | ------------- | ------ |
| /notifications/notify        | send email or slack notification | No | No |
| /users/new                   | create user | No | Yes |
| /users/settings/set          | set settings | Yes | Yes |
| /users/approve/{id}          | approve user id | No | No |
| /users/deny/{id}             | deny user id | No | No |
| /users/auth                  | authenticate user | No | Yes |
| /experiments                 | list user experiments | Yes | Yes |
| /experiments/queue           | list queued experiments | No | No |
| /experiments/{id}/files      | download experiment files | No | No |
| /experiments/{id}/results    | upload experiment result files | No | No |
| /experiments/new             | create new experiment | Yes | Yes |
| /uses/groups                 | list groups a user is in | Yes | Yes |
| /admin/users                 | users admin panel | No | No |
| /admin/groups                | groups admin panel | No | No |
| /groups/create               | create group | No | No |
| /groups/remove/{id}          | delete group | No | No |
| /groups/edit/{id}            | edit group | No | No |
| /users/groups/map            | map user to a group | No | No |


Authenticated means the user has to be signed in. Non-public means the endpoint is only available to UPHS IPs (meant for backend).

### Workflow
1. User creates account (/users/new), or logins (/users/auth)
2. User creates experiment by submitting form (/experiments/new). Uploaded files and the form, serialized as JSON, are placed in a folder like `UPLOAD_FOLDER/uid/submitted/eid` where UPLOAD_FOLDER is an environment variable, uid is a users ID, and eid is an experiment ID. In addition to the "submitted" namespace (meant for the backend to queue) there's an "editing" (ignored by backend) and "completed" namespace. The location of an experiments files determines the status.
3. IPP backend runs job, places output in `UPLOAD_FOLDER/uid/completed/eid`

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
- reset password
