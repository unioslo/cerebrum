#!/bin/sh
#
# Easily view the contents of all the involved cereconf.py files
#

source ~/.cerebrumrc

CERECONF_CUSTOM_PY="$CERECONF_CUSTOM/cereconf.py"
CERECONF_COMMON_PY="$CERECONF_PATH/common/cereconf.py"
CERECONF_GLOBAL_PY="$CERECONF_GLOBAL/cereconf.py"

if [[ -e "$CERECONF_CUSTOM_PY" ]]; then
  echo -e "\e[92m----------------------- $CERECONF_CUSTOM_PY --------------\e[0m\n"
  cat "$CERECONF_CUSTOM_PY"
  echo
fi

if [[ -e "$CERECONF_COMMON_PY" ]]; then
  echo -e "\e[92m----------------------- $CERECONF_COMMON_PY --------------\e[0m\n"
  cat "$CERECONF_COMMON_PY"
  echo
fi

if [[ -e "$CERECONF_GLOBAL_PY" ]]; then
  echo -e "\e[92m----------------------- $CERECONF_GLOBAL_PY --------------\e[0m\n"
  cat "$CERECONF_GLOBAL_PY"
  echo
fi
