#!/bin/sh -ex

# Copyright 2002, 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

# Extract path to ..
SRCDIR=`dirname $0`/..
SRCDIR=`cd $SRCDIR; pwd`

TESTDIR=$SRCDIR/testsuite

PYTHONPATH=$SRCDIR:$SRCDIR/Cerebrum
export PYTHONPATH

cd $SRCDIR

chmod u+x ./contrib/no/uio/import_OU.py 
chmod u+x ./contrib/no/uio/import_LT.py ./contrib/no/uio/import_FS.py
chmod u+x $TESTDIR/create_user.py ./contrib/generate_nismaps.py

echo "***** First time import *****"

./contrib/no/uio/import_OU.py -s $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py -p $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py -p $TESTDIR/FS-persons.dat

echo "***** Second time import, ie update *****"

./contrib/no/uio/import_OU.py -s $TESTDIR/LT-sted.dat

./contrib/no/uio/import_LT.py -p $TESTDIR/LT-persons.dat

./contrib/no/uio/import_FS.py -p $TESTDIR/FS-persons.dat

# FIXME: Add script to make new posix accounts from all existing persons


$TESTDIR/create_user.py || true
$TESTDIR/create_user.py 41023468091 || true
$TESTDIR/create_user.py 41023468415 || true

./contrib/generate_nismaps.py

exit 0

# arch-tag: 37a84fea-93e9-4377-826c-ff4ec28a23e7
