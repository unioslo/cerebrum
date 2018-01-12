#!/bin/bash
#
# Inotify script to trigger a command on file changes.
#
# Practically stolen as-is from Wolfgang Ziegler // fago
# https://gist.github.com/fago/9608238
#
# The script triggers the command as soon as a file event occurs. Events
# occurring during command execution are aggregated and trigger a single command
# execution only.
#
# Usage example: Trigger rsync for synchronizing file changes.
# ./watch.sh rsync -Cra --out-format='[%t]--%n' --delete SOURCE TARGET


######### Configuration #########

LOCAL_CEREBRUM_CONFIG_DIR=../cerebrum_config
EVENTS="CREATE,CLOSE_WRITE,DELETE,MODIFY,MOVED_FROM,MOVED_TO"
CEREBRUM_CONFIG_DIR=$1
COMMAND="rsync -az --delete $CEREBRUM_CONFIG_DIR/etc/ $LOCAL_CEREBRUM_CONFIG_DIR"

POST_COMMAND="touch ../dev-config/cereconf.py"


## Exclude Git (and other patterns if desired)
EXCLUDE='(\.git)'

## Whether to enable verbosity. If enabled, change events are output.
VERBOSE=0

##################################

if [ -z "$1" ]; then
 echo "Usage: $0 cerebrum_config repo-folder"
 exit 1;
fi

##
## Setup pipes. For usage with read we need to assign them to file descriptors.
##
RUN=$(mktemp -u)
mkfifo "$RUN"
exec 3<>$RUN

RESULT=$(mktemp -u)
mkfifo "$RESULT"
exec 4<>$RESULT

clean_up () {
  ## Cleanup pipes.
  rm $RUN
  rm $RESULT
}

## Execute "clean_up" on exit.
trap "clean_up" EXIT

echo "Syncing from $CEREBRUM_CONFIG_DIR"

# Do an initial sync
$($COMMAND)

echo "Initial sync complete!"

##
## Run inotifywait in a loop that is not blocked on command execution and ignore
## irrelevant events.
##
inotifywait -m -q -r -e $EVENTS --exclude $EXCLUDE --format '%w%f' $CEREBRUM_CONFIG_DIR | \
  while read FILE
  do
    if [ $VERBOSE -ne 0 ]; then
      echo [CHANGE] $FILE
    fi

    ## Clear $PID if the last command has finished.
    if [ ! -z "$PID" ] && ( ! ps -p $PID > /dev/null ); then
      PID=""
    fi

    ## If no command is being executed, execute one.
    ## Else, wait for the command to finish and then execute again.
    if [ -z "$PID" ]; then
      ## Execute the following as background process.
      ## It runs the command once and repeats if we tell him so.
	  ($COMMAND; $POST_COMMAND; while read -t0.001 -u3 LINE; do
	    echo running >&4
	    $COMMAND
	  done)&

      PID=$!
      WAITING=0
    else
      ## If a previous waiting command has been executed, reset the variable.
      if [ $WAITING -eq 1 ] && read -t0.001 -u4; then
        WAITING=0
      fi

      ## Tell the subprocess to execute the command again if it is not waiting
      ## for repeated execution already.
      if [ $WAITING -eq 0 ]; then
        echo "run" >&3
        WAITING=1
      fi

      ## If we are already waiting, there is nothing todo.
    fi
done