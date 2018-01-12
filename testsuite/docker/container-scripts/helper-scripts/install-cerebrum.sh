#!/usr/bin/env bash
cd /src
python setup.py install
cd /usr/local/share/cerebrum/design
python /usr/local/sbin/makedb.py $(cat $DOCKER_ROOT_DIR/extra-db-files/$INST.txt)
