#!/usr/bin/env python

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

def main():
    Cerebrum = Database.connect()
    makedbs(Cerebrum)


def makedbs(Cerebrum):
    for f in ('drop_core_tables.sql',
              'core_tables.sql',
              'mod_drop_posix_user.sql',
              'mod_posix_user.sql',
              'core_data.sql',
              #'pop.sql',
              'mod_drop_stedkode.sql',
              'mod_stedkode.sql'):
        runfile("design/%s" % f, Cerebrum)

def runfile(fname, Cerebrum):
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
        except:
            print "  CMD: [%s] -> " % ddl
            print "    database error:", sys.exc_info()[1]
        else:
            print "  ret: "+str(res)
    Cerebrum.commit()

if __name__ == '__main__':
    main()
