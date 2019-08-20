#!/usr/bin/env bash
#cd $DOCKER_ROOT_DIR/container-scripts/helper-scripts
pip install -r /src/testsuite/docker/test-config/test-requirements.txt
./create-db.sh
./install-cerebrum.sh
