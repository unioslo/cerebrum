#!/bin/sh
#
# Script for starting BOFH. All settings are read from ~/.cerebrumrc.
#
# For Cerebrum/USIT
#
# Changelog:
#   2013-06-26, Alexander Rødseth <rodseth@usit.uio.no>
#

source ~/.cerebrumrc

# Load the prompt as stored when starting bofhd
if [ -f ~/.bofhd_prompt ]; then
  source ~/.bofhd_prompt
fi

"$BOFH_BIN" \
  -u "$BOFH_USER" \
  --url "https://cere-utv01.uio.no:$BOFHD_PORT" \
  --set "console_prompt=$BOFH_PROMPT> " \
  "$@"

