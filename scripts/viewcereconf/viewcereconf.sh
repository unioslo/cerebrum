#!/bin/sh
#
# Easily view the contents of all the involved cereconf.py files
#
# Use -a or --all to also view the final configuration file
# (usually /cerebrum/uio/etcprod/cerebrum/cereconf.py)
#

source ~/.cerebrumrc

CERECONF_CUSTOM_PY="$CERECONF_CUSTOM/cereconf.py"
CERECONF_COMMON_PY="$CERECONF_PATH/common/cereconf.py"
CERECONF_GLOBAL_PY="$CERECONF_GLOBAL/cereconf.py"

if [[ -e "$CERECONF_CUSTOM_PY" ]]; then
  echo -e "\e[92m---------------- $CERECONF_CUSTOM_PY -----------\e[0m\n"
  cat "$CERECONF_CUSTOM_PY"
  echo
fi

if [[ -e "$CERECONF_COMMON_PY" ]]; then
  echo -e "\e[92m---------------- $CERECONF_COMMON_PY -----------\e[0m\n"
  cat "$CERECONF_COMMON_PY"
  echo
fi

if [[ -e "$CERECONF_GLOBAL_PY" ]]; then
  echo -e "\e[92m---------------- $CERECONF_GLOBAL_PY -----------\e[0m\n"
  cat "$CERECONF_GLOBAL_PY"
  echo
  if [[ "$1" == '-a' ]] || [[ "$1" == '--all' ]]; then
    CERECONF_SYSTEM_PY=`grep execfile "$CERECONF_GLOBAL_PY" | cut -d'"' -f2`
    if [[ -e "$CERECONF_SYSTEM_PY" ]]; then
      echo -e "\e[92m---------------- $CERECONF_SYSTEM_PY -----------\e[0m\n"
      cat "$CERECONF_SYSTEM_PY"
      echo
    fi
  fi
fi

if [[ "$CEREBRUM_INST" == 'tsd' ]]; then
  echo -e "\e[92m---------------- /cerebrum/uio/etc/cerebrum/cereconf.py -----------\e[0m\n"
  cat /cerebrum/uio/etc/cerebrum/cereconf.py
  echo

  echo -e "\e[92m---------------- $CEREBRUM_PATH/../cerebrum_sites/etc/tsd/cereconf.py -----------\e[0m\n"
  cat "$CEREBRUM_PATH/../cerebrum_sites/etc/tsd/cereconf.py"
  echo
fi

