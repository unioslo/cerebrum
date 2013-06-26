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

bofh \
  -u "$BOFH_USER" \
  --url "https://cere-utv01.uio.no:$BOFHD_PORT" \
  --set "console_prompt=$BOFH_PROMPT> " \
  "$@"

