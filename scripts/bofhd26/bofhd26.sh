#!/bin/sh

# BOFH with Python 2.6

source ~/.cerebrumrc

echo "Starting BOFHD for institution: $CEREBRUM_INST, using Python 2.6"

LD_LIBRARY_PATH=/local/lib /usr/bin/python2.6 "$BOFHD_PY" \
  -c "$BOFHD_CONFIG_DAT" \
  --logger-name=console \
  --logger-level=DEBUG \
  --port "$BOFHD_PORT" \
  "$@"

