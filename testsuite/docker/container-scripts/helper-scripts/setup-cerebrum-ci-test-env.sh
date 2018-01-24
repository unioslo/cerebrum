#!/usr/bin/env bash
#cd $DOCKER_ROOT_DIR/container-scripts/helper-scripts
pip install -r /src/testsuite/docker/test-config/test-requirements.txt
./create-db.sh
cp /src/testsuite/docker/test-config/cerebrum_path.py /usr/local/lib/python2.7
./install-cerebrum.sh
