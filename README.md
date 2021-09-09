# IPP API

## Overview

The API server contains all the business logic of the IPP, connecting the frontend interface to the [backend job-submission scripts](https://github.com/CBICA/IPP-be) and sqlite database (which stores user accounts and experiments). One set of routes (those marked public) are meant for the frontend, and the other set (marked not public) are meant for the backend. Backend routes only respond to localhost, and most frontend routes require you to pass a login token, however, some frontend routes don't require authentication (like /users/new).


| Endpoint | Description | Authenticated <small>(require login token)</small> | Public <small>(respond to any IP)</small> |
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
| /experiments/{id}/file       | download specific experiment file | Yes | Yes |
| /experiments/new             | create new experiment | Yes | Yes |
| /experiments/{id}/delete     | delete experiment input files | No | No |
| /experiments/{id}/failed     | mark experiment as failed | No | No |
| /files/delete                | delete specific file by path | No | No |
| /files/old                   | find files older than a specified number of days | No | No |
| /uses/groups                 | list groups a user is in | Yes | Yes |
| /admin/users                 | users admin panel | No | No |
| /admin/groups                | groups admin panel | No | No |
| /groups/create               | create group | No | No |
| /groups/remove/{id}          | delete group | No | No |
| /groups/edit/{id}            | edit group | No | No |
| /users/groups/map            | map user to a group | No | No |
| /version                     | get app version | No | No |
| /version/update              | update app version | No | No |
| /fe-version/update           | update frontend version | No | No |

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

### CentOS 6
To support CentOS 6 `./centos6/build.sh` converts python 3 to 2 then builds a standalone binary using pyinstaller
```sh
cd centos6/dist
# assumes you ran ../build.sh
FLASK_ENV=production UPLOAD_FOLDER=/var/uploads FLASK_RUN_PORT=8080 ./__init__
```

## Todo
- rate limiting endpoints (in application or with fail2ban?)
- reset password
