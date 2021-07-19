#!/bin/bash

set -e
cd $(dirname $0)
rm *.{py,spec} || true
rm -rf dist build helpers || true
cd ..
cp *.py centos6
cp -r helpers centos6/
cd centos6
/Users/tim/Library/Python/3.8/bin/3to2 -w -n __init__.py
/Users/tim/Library/Python/3.8/bin/3to2 -w -n helpers/__init__.py
docker build --build-arg requirements="$(cat ../requirements.txt | tr "\n" " ")" -t terf/centos6-pyinstaller .
docker run -it --rm -v $PWD:/opt/build -w /opt/build -e PYTHONPATH=/opt/build terf/centos6-pyinstaller --onefile --noconfirm __init__.py
