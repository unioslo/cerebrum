#!/bin/sh -ex

# Extract path to ..
SRCDIR=`dirname $0`/..
SRCDIR=`cd $SRCDIR; pwd`

TESTDIR=$SRCDIR/testsuite

PYTHONPATH=$SRCDIR:$SRCDIR/Cerebrum
export PYTHONPATH

cd $SRCDIR

chmod u+x ./makedb.py ./contrib/no/uio/import_OU.py 
chmod u+x ./contrib/no/uio/import_LT.py ./contrib/no/uio/import_FS.py
chmod u+x $TESTDIR/create_user.py ./contrib/generate_nismaps.py

./makedb.py

echo "***** First time import *****"

./contrib/no/uio/import_OU.py $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py $TESTDIR/FS-persons.dat

echo "***** Second time import, ie update *****"

./contrib/no/uio/import_OU.py $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py $TESTDIR/FS-persons.dat

# FIXME: Add script to make new posix accounts from all existing persons

./makedb.py $TESTDIR/posix_testuser.sql

$TESTDIR/create_user.py || true
$TESTDIR/create_user.py 41013462826 || true
$TESTDIR/create_user.py 41023468415 || true

./contrib/generate_nismaps.py

exit 0
