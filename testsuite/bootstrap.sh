#!/bin/sh -ex

# Extract path to ..
SRCDIR=`dirname $0`/..
SRCDIR=`cd $SRCDIR; pwd`

TESTDIR=$SRCDIR/testsuite

PYTHONPATH=$SRCDIR:$SRCDIR/Cerebrum
export PYTHONPATH

cd $SRCDIR

chmod u+x ./makedb.py

./makedb.py --drop
