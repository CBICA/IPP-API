#!/bin/bash

docker run -p 3330:5000 --name ipp-api --rm -it -v $PWD:/opt -v $PWD/tmp:/var/uploads terf/ipp-api
