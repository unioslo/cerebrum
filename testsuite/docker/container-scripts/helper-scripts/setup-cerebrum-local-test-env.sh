#!/usr/bin/env bash
cd $DOCKER_ROOT_DIR/container-scripts/helper-scripts
./create-db.sh
cp /src/testsuite/docker/test-config/cerebrum_path.py /usr/local/lib/python2.7
./setup-cerebrum-dev-env.sh
