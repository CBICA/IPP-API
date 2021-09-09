#!/bin/bash

set -eufx -o pipefail

cd $(dirname $0)/..
git pull
git checkout $1
shift
"$@"
