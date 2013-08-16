#!/bin/sh

source ~/.cerebrumrc

"$PYTHON_BIN" "$CEREBRUM_PATH/makedb.py" --only-insert-codes "$@" 
