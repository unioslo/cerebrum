#!/usr/bin/env bash

if [ -z "$1" ]; then
 echo "Usage: $0 <template_dir to sync from>"
 exit 1;
fi

cp ../Cerebrum/modules/templates/env.py .

./sync-templates.sh $1 &
docker run --rm  --security-opt seccomp=$(pwd)/chromium-seccomp.json -v "$PWD:/templates:z" -p 9222:9222 -p 5500:5500 -p 35729:35729 -it template-server python3 template-dev-server.py

kill 0
