#!/usr/bin/env bash
cd $DOCKER_ROOT_DIR/container-scripts/helper-scripts
./wait-for-db.sh
./setup-cerebrum-local-test-env.sh
cd /src
cp $TEST_CONFIG_DIR/$INST/pytest.ini .
eval $@