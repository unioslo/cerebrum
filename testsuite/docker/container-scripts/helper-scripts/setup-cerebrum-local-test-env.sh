#!/usr/bin/env bash
cd $DOCKER_ROOT_DIR/container-scripts/helper-scripts
./create-db.sh
./install-cerebrum-dev.sh
