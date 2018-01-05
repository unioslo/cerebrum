#!/usr/bin/env bash
IPYTHON_PROFILE_FOLDER=/root/.ipython/profile_default
cd $DOCKER_ROOT_DIR/scripts
./setup-cerebrum-dev-env.sh
mkdir -p $IPYTHON_PROFILE_FOLDER
cp $DOCKER_ROOT_DIR/dev-config/ipython_config.py $IPYTHON_PROFILE_FOLDER
PYTHONSTARTUP=$DOCKER_ROOT_DIR/dev-config/dev_shell.py  ipython
