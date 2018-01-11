#!/usr/bin/env bash
create-db.sh
cp /src/testsuite/docker/dev-config/cerebrum_path.py /usr/local/lib/python2.7
install-cerebrum-dev.sh

