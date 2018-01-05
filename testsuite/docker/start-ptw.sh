#!/usr/bin/env bash
cd $DOCKER_ROOT_DIR/scripts
./setup-cerebrum-local-test-env.sh
cd /src
cp $TEST_CONFIG_DIR/$INST/pytest.ini .
ptw