#!/bin/bash

set -e
cd $(dirname $0)
rm *.{py,spec} || true
rm -rf dist build helpers || true
cd ..
cp *.py centos6
cp -r helpers centos6/
cd centos6
docker build --progress=plain --build-arg requirements="$(cat ../requirements.txt | tr "\n" " ")" -t terf/centos6-pyinstaller .
docker run -it --rm -v $PWD:/opt/build -w /opt/build -e PYTHONPATH=/opt/build terf/centos6-pyinstaller --onefile --noconfirm __init__.py
