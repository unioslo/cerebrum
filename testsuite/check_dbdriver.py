# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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
import getopt

def create_tables():
    csr.execute("""CREATE TABLE foo (id NUMERIC(2)
    CONSTRAINT foo_pk PRIMARY KEY)""")
    csr.execute("""CREATE TABLE ref_foo (id NUMERIC(2)
    CONSTRAINT ref_foo_fk REFERENCES foo(id))""")

def check_insert_too_big_rollback():
    csr.execute("INSERT INTO foo values(1)")
    try:
        csr.execute("INSERT INTO foo values(111)")
    except:  # Known to fail, unfortunately DB-API don't specify exception to catch
        pass
    ok = "FAIL"
    try:
        csr.execute("SELECT id FROM foo WHERE id=1")
        for r in csr.fetchall():
            ok = "OK"
    except:
        pass
    print "check_insert_too_big_rollback: %s" % ok

def check_fk_failure_rollback():
    csr.execute("INSERT INTO foo values(2)")
    try:
        csr.execute("INSERT INTO ref_foo values(3)")
    except:  # Known to fail, unfortunately DB-API don't specify exception to catch
        pass
    ok = "FAIL"
    try:
        csr.execute("SELECT id FROM foo WHERE id=2")
        for r in csr.fetchall():
            ok = "OK"
    except:
        pass
    print "check_fk_failure_rollback: %s" % ok

def usage():
    print """Usage: $0 --connect-params arg --db-driver driver [--too-big-check | --fk-check]

    This script verifies if you database driver is broken in that it
    rollbacks transactions for you on an SQL error.  pyPgSQL.PgSQL is
    known to have this problem.
    
    Example: $0 --connect-params 'user="cerebrum", database="cerebrum"' --db-driver pyPgSQL.PgSQL --too-big-check
    Only one check may be ran pr try"""
    sys.exit(0)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['db-driver=', 'too-big-check',
                                                      'fk-check', 'connect-params='])
        if len(opts) == 0:
            usage()
    except getopt.GetoptError:
        usage()
    global csr
    for opt, val in opts:
        if opt in ('--db-driver',):
            exec("import %s as db_api" % val)
            db = eval("db_api.connect(%s)" % connect_params)
            csr = db.cursor()
            create_tables()
        elif opt in ('--connect-params',):
            connect_params = val
        elif opt in ('--too-big-check',):
            check_insert_too_big_rollback()
        elif opt in ('--fk-check',):
            check_fk_failure_rollback()

if __name__ == '__main__':
    main()

# arch-tag: e099252d-1bb8-4cdb-822d-754c66c02bc5
