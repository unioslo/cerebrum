#!/usr/bin/env bash
cd $DOCKER_ROOT_DIR/scripts
./create-db.sh
cp /src/testsuite/docker/test-config/cerebrum_path.py /usr/local/lib/python2.7
./install-cerebrum.sh

