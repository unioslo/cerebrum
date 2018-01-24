#!/usr/bin/env bash
cd /src
pip install -e .
cd /src/design
python /src/makedb.py $(cat $DOCKER_ROOT_DIR/extra-db-files/$INST.txt)
