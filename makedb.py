#!/usr/bin/env python2.2

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

import sys
import re
import traceback
import getopt
import os

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

def usage(exitcode=0):
    print """makedb.py [options] [sql-file ...]

  --extra-file=file
        For each phase, do SQL statements for core Cerebrum first,
        then SQL from 'file'.  This option can be specified more than
        once; for each phase, the additional 'file's will then be run
        in the order they're specified.
  --only-insert-codes
        Make sure all code values for the current configuration of
        cereconf.CLASS_CONSTANTS have been inserted into the database.
  --drop
        Perform only the 'drop' phase.
        WARNING: This will remove tables and the data they're holding
                 from your database.
  -d | --debug
  -c file | --country-file=file

If one or more 'sql-file' arguments are given, each phase will include
only statements from those files.  The statements for core Cerebrum
won't be included.

"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dc:',
                                   ['debug', 'help', 'drop',
                                    'only-insert-codes', 'country-file=',
                                    'extra-file='])
    except getopt.GetoptError:
        usage(1)

    debug = 0
    do_drop = False
    extra_files = []
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
    if db_user is None:
        db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
        if db_user is not None:
            print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
            print "Will use regular 'user' (%s) instead." % db_user
    Cerebrum = Factory.get('Database')(user=db_user)
    Cerebrum.cl_init(change_program="makedb")
    for opt, val in opts:
        if opt == '--help':
            usage()
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt == '--drop':
            # We won't drop any tables (which might be holding data)
            # unless we're explicitly asked to do so.
            do_drop = True
        elif opt == '--only-insert-codes':
            insert_code_values(Cerebrum)
            sys.exit()
        elif opt == '--extra-file':
            extra_files.append(val)
        elif opt in ('-c', '--country-file'):
            read_country_file(val, Cerebrum)
            sys.exit()

    # By having two leading spaces in the '  insert' literal below, we
    # make sure that the 'insert code values' phase won't execute any
    # statements from .sql files.
    #
    # This safeguard works because runfile(), which is used to process
    # .sql files, will collapse any sequence of whitespace into a
    # single space before it tries to decide what phase a statement
    # belongs in.
    order = ('code', '  insert', 'main')
    if args:
        do_bootstrap = False
        files = args
    else:
        do_bootstrap = True
        files = get_filelist(Cerebrum, extra_files)

    # With --drop, all we should do is run the 'drop' category
    # statements.  Reverse the SQL file order to drop modules
    # depending on core first; statement order in each file is NOT
    # reversed, though.
    if do_drop:
        fr = files[:]
        fr.reverse()
        for f in fr:
            runfile(f, Cerebrum, debug, 'drop')
        sys.exit(0)

    for phase in order:
        if phase == '  insert':
            insert_code_values(Cerebrum)
        else:
            for f in files:
                runfile(f, Cerebrum, debug, phase)
    if do_bootstrap:
        makeInitialUsers(Cerebrum)

def read_country_file(fname, db):
    f = file(fname, "r")
    for line in f.readlines():
        if line[0] == '#':
            continue
        dta = [x.strip() for x in line.split("\t") if x.strip() <> ""]
        if len(dta) == 4:
            cols = {
                'code_str': dta[0],
                'country': dta[2],
                'phone_prefix': dta[3],
                'description': dta[2]
                }
            db.execute("""
            INSERT INTO [:table schema=cerebrum name=country_code]
              (code, %s) VALUES
              ([:sequence schema=cerebrum name=code_seq op=next], %s)""" % (
                ", ".join(cols.keys()), ", ".join([":%s" % t for t in
                                                   cols.keys()])), cols)
    db.commit()

def insert_code_values(Cerebrum):
    const = Factory.get('Constants')(Cerebrum)
    print "Inserting code values."
    new, total = const.initialize()
    print "  Inserted %d new codes (new total: %d)." % (new, total)
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
    a.set_password(cereconf.INITIAL_ACCOUNTNAME_PASSWORD)
    a.write_db()

    g = Group.Group(Cerebrum)
    g.populate(a.entity_id, co.group_visibility_all,
               cereconf.INITIAL_GROUPNAME, parent=eg)
    g.write_db()
    g.add_member(a.entity_id, co.entity_account, co.group_memberop_union)
    Cerebrum.commit()

def get_filelist(Cerebrum, extra_files=[]):
    core_files = ['core_tables.sql']
    files = core_files[:]
    files.extend(extra_files)
    ret = []
    ddl_dir = os.path.dirname(sys.argv[0])+"/"+cereconf.CEREBRUM_DDL_DIR
    for f in files:
        if '/' in f:
            ret.append(f)
        else:
            if f in core_files:
                ret.append(os.path.join(ddl_dir, f))
            else:
                ret.append(f)
    return ret

def runfile(fname, Cerebrum, debug, phase):
    print "Reading file (phase=%s): <%s>" % (phase, fname)
    # Run both the generic (e.g. 'main') and driver-specific
    # (e.g. 'main/Oracle' categories for this phase in one run.
    phase_driver = "/".join((phase, Cerebrum.__class__.__base__.__name__))
    f = file(fname)
    text = "".join(f.readlines())
    long_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
    text = re.sub(long_comment, "", text)
    line_comment = re.compile(r"--.*")
    text = re.sub(line_comment, "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.split(";")
    NO_CATEGORY, WRONG_CATEGORY, CORRECT_CATEGORY = 1, 2, 3
    state = NO_CATEGORY
    output_col = None
    max_col = 78
    for stmt in text:
        stmt = stmt.strip()
        if not stmt:
            continue
        if state == NO_CATEGORY:
            (type_id, value) = stmt.split(":", 1)
            if type_id <> 'category':
                raise ValueError, \
                      "Illegal type_id in file %s: %s" % (fname, i)
            if value in (phase, phase_driver):
                state = CORRECT_CATEGORY
            else:
                state = WRONG_CATEGORY
        elif state == WRONG_CATEGORY:
            state = NO_CATEGORY
            continue
        elif state == CORRECT_CATEGORY:
            state = NO_CATEGORY
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
                if not output_col:
                    status = "    " + status
                    output_col = 0
                sys.stdout.write(status)
                output_col += len(status)
                if output_col >= max_col:
                    sys.stdout.write("\n")
                    output_col = 0
                sys.stdout.flush()
                Cerebrum.commit()
    if state <> NO_CATEGORY:
        raise ValueError, \
              "Found more category specs than statements in file %s." % fname
    if output_col is not None:
        print

if __name__ == '__main__':
    main()
