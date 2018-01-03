#!/usr/bin/env bash
./setup-cerebrum.sh
py.test --cov=/src --cov-report xml:/src/testresults/${INST}_coverage.xml \
            --junitxml=/src/testresults/${INST}_junit.xml \
            $(cat ${INST_DIR}/pytest_tests.txt)