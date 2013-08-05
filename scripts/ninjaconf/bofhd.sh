#!/bin/sh
#
# Script for starting BOFHD. All settings are read from ~/.cerebrumrc.
#
# CEREBRUM_INST can be set to an institution (defaults to uio)
#
# For Cerebrum/USIT
#
# Changelog:
#   2013-06-26, Alexander Rødseth <rodseth@usit.uio.no>
#

source ~/.cerebrumrc

echo "Starting BOFHD for institution: $CEREBRUM_INST"

"$PYTHON_BIN" "$BOFHD_PY" \
  -c "$BOFHD_CONFIG_DAT" \
  --logger-name=console \
  --logger-level=DEBUG \
  --port "$BOFHD_PORT" \
  "$@"
