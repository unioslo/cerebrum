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

from Cerebrum import Database
from Cerebrum import Constants
from Cerebrum import Group
from Cerebrum import Account
from Cerebrum import cereconf

from Cerebrum import Entity

def main():
    ignoreerror = False
    global Cerebrum
    Cerebrum = Database.connect()
    if len(sys.argv) >= 2:
        for f in sys.argv[1:]:
            runfile(f, Cerebrum, ignoreerror)
    else:
        makedbs(Cerebrum, ignoreerror)
    makeInitialUsers()

def makeInitialUsers():
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

def makedbs(Cerebrum, ignoreerror):
    for f in ('drop_mod_stedkode.sql',
              'drop_mod_nis.sql',
              'drop_mod_posix_user.sql',
              'drop_core_tables.sql',
              'core_tables.sql',
              'mod_posix_user.sql',
              'mod_nis.sql',
              'core_data.sql',
              'mod_stedkode.sql'
              ):
        runfile("design/%s" % f, Cerebrum, ignoreerror)

def runfile(fname, Cerebrum, ignoreerror):
    print "Reading file: <%s>" % fname
    f = file(fname)
    text = "".join(f.readlines())
    long_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
    text = re.sub(long_comment, "", text)
    line_comment = re.compile(r"--.*")
    text = re.sub(line_comment, "", text)
    text = re.sub(r"\s+", " ", text)
    for ddl in text.split(";"):
        ddl = ddl.strip()
        if not ddl:
            continue
        try:
            res = Cerebrum.execute(ddl)
            if ignoreerror:
                Cerebrum.commit()
        except:
            print "  CMD: [%s] -> " % ddl
            print "    database error:", sys.exc_info()[1]
        else:
            print "  ret: "+str(res)
    if not ignoreerror:
        Cerebrum.commit()

if __name__ == '__main__':
    main()
