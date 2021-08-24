#!/bin/bash

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <retention-in-days>"
    exit 1
fi

for f in $(curl -s "http://localhost:5000/files/old?days=$1"); do
    curl -X POST -d "path=$f" "http://localhost:5000/files/delete"
done
