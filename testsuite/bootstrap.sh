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

MAKEDB=./makedb.py

chmod u+x $MAKEDB

EXTRA="\
     --extra-file=design/mod_posix_user.sql \
     --extra-file=design/mod_stedkode.sql \
     --extra-file=design/bofhd_tables.sql \
     --extra-file=design/bofhd_auth.sql \
     --extra-file=design/mod_changelog.sql"

$MAKEDB --drop $EXTRA && $MAKEDB $EXTRA

# arch-tag: 1034aa73-c943-4a0d-a638-d057175c9c11
