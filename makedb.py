#!/usr/bin/env python2.2

# Copyright 2002 University of Oslo, Norway
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

import sys
import re
import traceback
import getopt
import os

import cereconf
from Cerebrum.Utils import Factory

def main():
    opts, args = getopt.getopt(sys.argv[1:], 'd', ['debug'])

    debug = 0
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1

    Cerebrum = Factory.get('Database')(
        user=cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner'])

    if args:
        for f in args:
            runfile(f, Cerebrum, debug, None)
    else:
        files = get_filelist(Cerebrum)
        fr = files[:]
        fr.reverse()
        for f in fr:
            runfile(os.path.join(CEREBRUM_DDL_DIR, f), Cerebrum, debug, 'drop')
        for f in files:
            runfile(os.path.join(CEREBRUM_DDL_DIR, f), Cerebrum, debug, 'code')
        insert_code_values(Cerebrum)
        for f in files:
            runfile(os.path.join(CEREBRUM_DDL_DIR, f), Cerebrum, debug, 'main')
        makeInitialUsers(Cerebrum)

def insert_code_values(Cerebrum):
    const = Factory.get('Constants')(Cerebrum)
    print "Inserting code values."
    const.initialize()
    Cerebrum.commit()

def makeInitialUsers(Cerebrum):
    print "Creating initial entities."
    from Cerebrum import Constants
    from Cerebrum import Group
    from Cerebrum import Account
    from Cerebrum import Entity
    co = Constants.Constants(Cerebrum)
    eg = Entity.Entity(Cerebrum)
    eg.populate(co.entity_group)
    eg.write_db()

    ea = Entity.Entity(Cerebrum)
    ea.populate(co.entity_account)
    ea.write_db()

    # TODO:  These should have a permanent quarantine and be non-visible
    a = Account.Account(Cerebrum)
    a.populate(cereconf.INITIAL_ACCOUNTNAME, co.entity_group,
               eg.entity_id, int(co.account_program), ea.entity_id,
               None, parent=ea)
    a.write_db()

    g = Group.Group(Cerebrum)
    g.populate(a, co.group_visibility_all, cereconf.INITIAL_GROUPNAME,
               parent=eg)
    g.write_db()

    Cerebrum.commit()


CEREBRUM_DDL_DIR = "design"

def get_filelist(Cerebrum):
    # Need to import Database.py for testing whether the database
    # class we're using is an Oracle (sub)class.
    from Cerebrum import Database
    files = ['core_tables.sql',
             'mod_posix_user.sql',
             'mod_nis.sql',
             'mod_stedkode.sql'
             ]
    if isinstance(Cerebrum, Database.Oracle):
        files.extend(['drop_oracle_grants.sql', 'oracle_grants.sql'])
    return files

def runfile(fname, Cerebrum, debug, key=None):
    print "Reading file (key=%s): <%s>" % (key, fname)
    f = file(fname)
    text = "".join(f.readlines())
    long_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
    text = re.sub(long_comment, "", text)
    line_comment = re.compile(r"--.*")
    text = re.sub(line_comment, "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.split(";")
    for n in range(0, len(text), 2):
        text[n] = text[n].strip()
        if n == len(text) - 1:
            break
        (type_id, value) =  text[n].split(":")
        if type_id <> 'category':
            raise RuntimeError, "Illegal type_id in: %s" % text[n]
        if key is not None and key <> value:
            continue
        stmt = text[n+1].strip()
        if not stmt:
            continue
        try:
            status = "."
            try:
                Cerebrum.execute(stmt)
            except Cerebrum.DatabaseError:
                status = "E"
                print "\n  ERROR: [%s]" % stmt
                if debug:
                    print "  Database error: ",
                    if debug >= 2:
                        # Re-raise error, causing us to (at least)
                        # break out of this for loop.
                        raise
                    else:
                        traceback.print_exc(file=sys.stdout)
        finally:
            sys.stdout.write(status)
            sys.stdout.flush()
            Cerebrum.commit()
    print

if __name__ == '__main__':
    main()
