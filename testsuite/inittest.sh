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

./makedb.py

echo "***** First time import *****"

./contrib/no/uio/import_OU.py $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py $TESTDIR/FS-persons.dat

echo "***** Second time import, ie update *****"

./contrib/no/uio/import_OU.py $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py $TESTDIR/FS-persons.dat

# FIXME: Add script to make new posix accounts from existing persons

./contrib/generate_nismaps.py > $TESTDIR/nis-passwd.out
