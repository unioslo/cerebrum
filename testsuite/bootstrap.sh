#!/bin/sh -ex

# Extract path to ..
SRCDIR=`dirname $0`/..
SRCDIR=`cd $SRCDIR; pwd`

TESTDIR=$SRCDIR/testsuite

PYTHONPATH=$SRCDIR:$SRCDIR/Cerebrum
export PYTHONPATH

cd $SRCDIR

MAKEDB=./makedb.py

chmod u+x $MAKEDB

EXTRA="\
     --extra-file=design/mod_posix_user.sql \
     --extra-file=design/mod_stedkode.sql \
     --extra-file=design/bofhd_tables.sql \
     --extra-file=design/bofhd_auth.sql \
     --extra-file=design/mod_changelog.sql"

$MAKEDB --drop $EXTRA && $MAKEDB $EXTRA
