#!/bin/bash

# This script allows you to cd into any directory, git pull, then checkout anything
# the rest of the args are exec'd as a mechanism to restart the server

set -eufx -o pipefail

cd $1
shift
git pull
git checkout $1
shift
"$@"
