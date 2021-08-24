#!/bin/bash

set -euo pipefail

for user in $(curl -s "http://localhost:5000/users/list?awaiting_approval=1" | jq -c ".[]"); do
    email=$(echo $user | jq '.email')
    uid=$(echo $user | jq '.id')
    settings=$(echo $user | jq -r '.settings|to_entries|map("\(.key)=\(.value|tostring)")|.[]')
    echo "A new user, ${email}, has requested approval"
    echo $settings
    read -p "Do you want to approve? " -n 1 -r
    echo # (optional) move to a new line
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        curl -s "http://localhost:5000/users/approve/${uid}" > /dev/null
        echo "Approved user ${email}"
    else
        curl -s "http://localhost:5000/users/deny/${uid}" > /dev/null
        echo "Denied user ${email}"
    fi
done
