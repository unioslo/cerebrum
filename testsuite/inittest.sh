#!/bin/sh -ex

# Extract path to ..
SRCDIR=`dirname $0`/..
SRCDIR=`cd $SRCDIR; pwd`

TESTDIR=$SRCDIR/testsuite

PYTHONPATH=$SRCDIR:$SRCDIR/Cerebrum
export PYTHONPATH

cd $SRCDIR
./makedb.py

./contrib/no/uio/import_OU.py $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py $TESTDIR/FS-persons.dat
