#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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
from Cerebrum.Utils import Factory, dyn_import
from Cerebrum import Metainfo
from Cerebrum import Errors
import Cerebrum

all_ok = True


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
        Does not create tables.
  --update-codes
        Like --only-insert-codes, but will remove constants that
        exists in the database, but not in CLASS_CONSTANTS (subject to
        FK constraints).
  --drop
        Perform only the 'drop' phase.
        WARNING: This will remove tables and the data they're holding
                 from your database.
  --stage
        Only perform this stage in the files.
  -d | --debug
  -c file | --country-file=file

If one or more 'sql-file' arguments are given, each phase will include
only statements from those files.  The statements for core Cerebrum
won't be included.

"""
    sys.exit(exitcode)


def main():
    global meta
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dc:',
                                   ['debug', 'help', 'drop', 'update-codes',
                                    'only-insert-codes', 'country-file=',
                                    'extra-file=', 'stage='])
    except getopt.GetoptError:
        usage(1)

    debug = 0
    do_drop = False
    stage = None
    extra_files = []
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
    if db_user is None:
        db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
        if db_user is not None:
            print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
            print "Will use regular 'user' (%s) instead." % db_user
    db = Factory.get('Database')(user=db_user)
    db.cl_init(change_program="makedb")

    # Force all Constants-writing to use the same db-connection
    # as CREATE TABLE++
    # TDB: could _CerebrumCode have a classmethod to do this, and
    # also empty all cached constants?
    from Cerebrum.Constants import _CerebrumCode
    _CerebrumCode.sql.fset(None, db)

    meta = Metainfo.Metainfo(db)
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
            insert_code_values(db, debug=debug)
            check_schema_versions(db)
            sys.exit()
        elif opt == '--update-codes':
            insert_code_values(db, delete_extra_codes=True, debug=debug)
            check_schema_versions(db)
            sys.exit()
        elif opt == '--stage':
            stage = val
        elif opt == '--extra-file':
            extra_files.append(val)
        elif opt in ('-c', '--country-file'):
            read_country_file(val)
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
    if stage:
        order = (stage,)
    if args:
        do_bootstrap = False
        files = args
    else:
        do_bootstrap = True
        files = get_filelist(db, extra_files)

    # With --drop, all we should do is run the 'drop' category
    # statements.  Reverse the SQL file order to drop modules
    # depending on core first; statement order in each file is NOT
    # reversed, though.
    if do_drop:
        fr = files[:]
        fr.reverse()
        for f in fr:
            runfile(f, db, debug, 'drop')
        sys.exit(0)

    for phase in order:
        if phase == '  insert':
            insert_code_values(db, debug=debug)
        else:
            for f in files:
                runfile(f, db, debug, phase)
    if do_bootstrap:
        # When bootstrapping, make sure the versions match
        check_schema_versions(db, strict=True)
        makeInitialUsers(db)
        db.commit()
    else:
        check_schema_versions(db)
    if not all_ok:
        sys.exit(1)


def read_country_file(fname):
    const = Factory.get('Constants')()
    f = file(fname, "r")
    for line in f.readlines():
        if line[0] == '#':
            continue
        dta = [x.strip() for x in line.split("\t") if x.strip() <> ""]
        if len(dta) == 4:
            code_str, foo, country, phone_prefix = dta
            code_obj = const.Country(code_str, country, phone_prefix,
                                     description=country)
            code_obj.insert()
    const.commit()


def insert_code_values(db, delete_extra_codes=False, debug=False):
    const = Factory.get('Constants')()
    print "Inserting code values."
    try:
        stats = const.initialize(delete=delete_extra_codes)
    except db.DatabaseError:
        traceback.print_exc(file=sys.stdout)
        print "Error initializing constants, check that you include " +\
              "the sql files referenced by CLASS_CONSTANTS"
        sys.exit(1)
    if delete_extra_codes:
        print "  Inserted %(inserted)d new codes (new total: %(total)d), "\
            "updated %(updated)d, deleted %(deleted)d" % stats
    else:
        print "  Inserted %(inserted)d new codes (new total: %(total)d), "\
            "updated %(updated)d, superfluous %(superfluous)d" % stats
    if debug and stats['details']:
        print "  Details:\n    %s" % "\n    ".join(stats['details'])
    const.commit()


def makeInitialUsers(db):
    print "Creating initial entities."
    from Cerebrum import Constants
    from Cerebrum import Group
    from Cerebrum import Account
    from Cerebrum import Entity
    co = Constants.Constants()
    eg = Entity.Entity(db)
    eg.populate(co.entity_group)
    eg.write_db()

    ea = Entity.Entity(db)
    ea.populate(co.entity_account)
    ea.write_db()

    def false(*args):
        return False

    # TODO:  These should have a permanent quarantine and be non-visible

    # Use Account.Account to avoid getting the wrong Account Mixins
    # fiddling with the bootstrap account. Every instance may use this
    # account as they see fit, but have to append functionality
    # manually afterwards. makedb an account that can be created with
    # a fully populated cereconf, but an empty database(which may
    # break a lot of Mixins).

    a = Account.Account(db)
    a.illegal_name = false
    a.populate(cereconf.INITIAL_ACCOUNTNAME, co.entity_group,
               eg.entity_id, int(co.account_program), ea.entity_id,
               None, parent=ea)
    # Get rid of errors because of missing prerequisites for password
    # mechanisms not needed for initial setup.
    #
    # TBD: implement cereconf.INITIAL_PASSWORD_MECHANISM?
    method = co.auth_type_md5_crypt
    a.affect_auth_types(method)
    enc = a.encrypt_password(method, cereconf.INITIAL_ACCOUNTNAME_PASSWORD)
    a.populate_authentication_type(method, enc)
    a.write_db()

    g = Group.Group(db)
    g.illegal_name = false
    g.populate(a.entity_id, co.group_visibility_all,
               cereconf.INITIAL_GROUPNAME, parent=eg)
    g.write_db()
    g.add_member(a.entity_id)
    db.commit()


def check_schema_versions(db, strict=False):
    modules = {
        'ad': 'Cerebrum.modules.ADObject',
        'changelog': 'Cerebrum.modules.ChangeLog',
        'dns': 'Cerebrum.modules.dns',
        'email': 'Cerebrum.modules.Email',
        'entity_trait': 'Cerebrum.modules.EntityTrait',
        'note': 'Cerebrum.modules.Note',
        'password_history': 'Cerebrum.modules.PasswordHistory',
        'posixuser': 'Cerebrum.modules.PosixUser',
        'stedkode': 'Cerebrum.modules.no.Stedkode',
    }
    meta = Metainfo.Metainfo(db)
    for name, value in meta.list():
        if name == Metainfo.SCHEMA_VERSION_KEY:
            if not Cerebrum._version == value:
                print "WARNING: cerebrum version %s does not match schema version %s" % (
                    "%d.%d.%d" % Cerebrum._version,
                    "%d.%d.%d" % value)
                if strict:
                    exit(1)
        elif name[:10] == 'sqlmodule_':
            name = name[10:]
            if not modules.has_key(name):
                # print "WARNING: unknown module %s" % name
                # if strict: exit(1)
                continue
            try:
                module = dyn_import(modules[name])
                version = module.__version__
            except Exception, e:
                print "ERROR: can't find version of module %s: %s" % (
                    name, e)
                continue
            if not module.__version__ == value:
                print "WARNING: module %s version %s does not match schema version %s" % (
                    name, module.__version__, value)
                if strict:
                    exit(1)
        else:
            print "ERROR: unknown metainfo %s: %s" % (
                name, value)
            if strict:
                exit(1)


def get_filelist(db, extra_files=[]):
    core_files = ['core_tables.sql']
    files = core_files[:]
    files.extend(extra_files)
    ret = []
    if cereconf.CEREBRUM_DDL_DIR.startswith("/"):
        ddl_dir = cereconf.CEREBRUM_DDL_DIR
    else:
        ddl_dir = os.path.dirname(sys.argv[0])
        if ddl_dir == '':
            ddl_dir = '.'
        ddl_dir += "/" + cereconf.CEREBRUM_DDL_DIR
    for f in files:
        if '/' in f:
            ret.append(f)
        else:
            if f in core_files:
                ret.append(os.path.join(ddl_dir, f))
            else:
                ret.append(f)
    return ret


def runfile(fname, db, debug, phase):
    global all_ok
    print "Reading file (phase=%s): <%s>" % (phase, fname)
    f = file(fname)
    text = f.readlines()
    long_comment_start = re.compile(r"/\*", re.DOTALL)
    long_comment_stop = re.compile(r".*?\*/", re.DOTALL)
    long_line_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
    line_comment = re.compile(r"--.*")
    sc_pat_repl = re.compile(r';\s*')
    sc_pat = re.compile(r'.*;\s*')
    kill_newline_repl = re.compile('\n+')
    kill_spaces_repl = re.compile('\s+')


    function_join_mode = False
    skip_mode = False
    tmp = []
    join_str = ''

    # Iterate through all lines in the file, and generate statements
    # from the lines. We need combine lines like this, in order to support
    # functions.
    for x in text:
        x = kill_newline_repl.sub('', x)
        x = kill_spaces_repl.sub(' ', x)
        # Skip long comments
        if re.match(long_comment_start, x):
            skip_mode = True
            continue
        elif re.match(long_comment_stop, x):
            skip_mode = False
            continue
        elif skip_mode:
            continue
        # Skip line comments
        elif re.match(line_comment, x) or re.match(long_line_comment, x):
            continue
        # Handle functions correctly
        elif 'FUNCTION' in x and not 'DROP FUNCTION' in x:
            function_join_mode = True
            join_str += x
        elif 'LANGUAGE' in x:
            function_join_mode = False
            join_str += sc_pat_repl.sub('', x)
            tmp.append(join_str)
            join_str = ''
        elif function_join_mode:
            join_str += x
        # Handle everything else
        else:
            if not sc_pat.match(x):
                join_str += x
            else:
                join_str += sc_pat_repl.sub('', x)
                tmp.append(join_str)
                join_str = ''
    text = tmp
    
    NO_CATEGORY, WRONG_CATEGORY, CORRECT_CATEGORY, SET_METAINFO = 1, 2, 3, 4
    state = NO_CATEGORY
    output_col = None
    max_col = 78
    metainfo = {}
    for stmt in text:
        stmt = stmt.strip()
        if not stmt:
            continue
        if state == NO_CATEGORY:
            (type_id, for_phase) = stmt.split(":", 1)
            if type_id <> 'category':
                raise ValueError, \
                    "Illegal type_id in file %s: %s" % (fname, type_id)
            for_rdbms = None
            if for_phase == 'metainfo':
                state = SET_METAINFO
                continue
            if '/' in for_phase:
                for_phase, for_rdbms = for_phase.split("/", 1)
            if for_phase == phase and (for_rdbms is None or
                                       for_rdbms == db.rdbms_id):
                state = CORRECT_CATEGORY
            else:
                state = WRONG_CATEGORY
        elif state == WRONG_CATEGORY:
            state = NO_CATEGORY
            continue
        elif state == SET_METAINFO:
            state = NO_CATEGORY
            (key, val) = stmt.split("=", 1)
            metainfo[key] = val
        elif state == CORRECT_CATEGORY:
            state = NO_CATEGORY
            try:
                status = "."
                try:
                    db.execute(stmt)
                except db.DatabaseError:
                    all_ok = False
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
                db.commit()
    if (phase == 'main' or phase == 'metainfo'):
        if metainfo['name'] == 'core':
            name = Metainfo.SCHEMA_VERSION_KEY
            version = tuple([int(i) for i in metainfo['version'].split('.')])
        else:
            name = 'sqlmodule_%s' % metainfo['name']
            version = metainfo['version']
        meta.set_metainfo(name, version)
        db.commit()
    if state <> NO_CATEGORY:
        raise ValueError, \
            "Found more category specs than statements in file %s." % fname
    if output_col is not None:
        print

if __name__ == '__main__':
    main()

# arch-tag: 4b01504e-d98e-4331-acea-9e2d0478a18f
