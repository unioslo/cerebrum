#!/usr/bin/env bash
cd $DOCKER_ROOT_DIR/scripts
./setup-cerebrum-ci-test-env.sh
cd /src
cp $TEST_CONFIG_DIR/$INST/pytest.ini .
py.test --cov=/src --cov-report xml:/src/testresults/${INST}_coverage.xml \
            --junitxml=/src/testresults/${INST}_junit.xml