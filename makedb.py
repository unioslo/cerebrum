#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
"""
Management tool for Cerebrum's database.

This script is the main tool for managing Cerebrum's postgres database. It
supports creating and updating the required tables and Cerebrum constants. The
script is in most situations required to be run when setting up and when
upgrading Cerebrum.

The database structure for the various Cerebrum modules are defined in::

    design/*.sql

The files include SQL operations for the different stages/phases of management:

    - metainfo, like the version of the db-table

    - main, for when setting up the database, e.g. creating tables

    - code, for setting up access in the database. Only used for Oracle, which
      has not been used for a while.

    - drop, for when removing tables and other data


Note that the SQL file parser are somewhat limited. For instance, long comments
(/* ... */) can not start or stop on the same line as proper SQL statements,
but have to be on their own lines.

TODO: Describe the format of the SQL definitions, or add a reference to where
that is located.
"""
from __future__ import print_function

import getopt
import os
import sys
import traceback

import Cerebrum
from Cerebrum import Metainfo
from Cerebrum.database import sql_parser
from Cerebrum.Utils import Factory, dyn_import

import cereconf

all_ok = True


def usage(exitcode=0):
    print(__doc__)
    print("""Usage: makedb.py [options] [sql-file ...]

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

  -d --debug
        Print out more debug information. If added twice, you will get even
        more information.

  -c file | --country-file=file

If one or more 'sql-file' arguments are given, each phase will include
only statements from those files.  The statements for core Cerebrum
won't be included.

""")
    sys.exit(exitcode)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dc:h',
                                   ['debug', 'help', 'drop', 'update-codes',
                                    'only-insert-codes', 'country-file=',
                                    'clean-codes-from-cl',
                                    'extra-file=', 'stage='])
    except getopt.GetoptError as e:
        print(e)
        usage(1)

    debug = 0
    do_drop = False
    stage = None
    extra_files = []
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
    if db_user is None:
        db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
        if db_user is not None:
            print("'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA.")
            print("Will use regular 'user' (%s) instead." % db_user)
    db = Factory.get('Database')(user=db_user)
    db.cl_init(change_program="makedb")

    # Force all Constants-writing to use the same db-connection
    # as CREATE TABLE++
    # TDB: could _CerebrumCode have a classmethod to do this, and
    # also empty all cached constants?
    from Cerebrum.Constants import _CerebrumCode
    _CerebrumCode.sql.fset(None, db)

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt == '--drop':
            # We won't drop any tables (which might be holding data)
            # unless we're explicitly asked to do so.
            do_drop = True
        elif opt == '--clean-codes-from-cl':
            clean_codes_from_change_log(db)
            sys.exit()
        elif opt == '--only-insert-codes':
            insert_code_values(db)
            check_schema_versions(db)
            sys.exit()
        elif opt == '--update-codes':
            insert_code_values(db, delete_extra_codes=True)
            check_schema_versions(db)
            sys.exit()
        elif opt == '--stage':
            stage = val
        elif opt == '--extra-file':
            extra_files.append(val)
        elif opt in ('-c', '--country-file'):
            read_country_file(val)
            sys.exit()
        else:
            print("Unknown argument: %s" % opt)
            usage(1)

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
            insert_code_values(db)
        else:
            for f in files:
                runfile(f, db, debug, phase)
    if do_bootstrap:
        # When bootstrapping, make sure the versions match
        check_schema_versions(db, strict=True)
        make_inital_users(db)
        db.commit()
    else:
        check_schema_versions(db)
    if not all_ok:
        sys.exit(1)


def read_country_file(fname):
    const = Factory.get('Constants')()
    with open(fname, "r") as f:
        for line in f.readlines():
            if line[0] == '#':
                continue
            dta = [x.strip() for x in line.split("\t") if x.strip() != ""]
            if len(dta) == 4:
                code_str, foo, country, phone_prefix = dta
                code_obj = const.Country(code_str, country, phone_prefix,
                                         description=country)
                code_obj.insert()
    const.commit()


def insert_code_values(db, delete_extra_codes=False):
    def do(kind):
        const = Factory.get(kind)(db)
        try:
            stats = const.initialize(delete=delete_extra_codes)
        except db.DatabaseError:
            traceback.print_exc(file=sys.stdout)
            print("Error initializing constants, check that you include "
                  "the sql files referenced by CLASS_CONSTANTS and "
                  "CLASS_CL_CONSTANTS")
            sys.exit(1)
        if delete_extra_codes:
            print('  Inserted {inserted} new {kind} (new total: {total}), '
                  'updated {updated}, deleted {deleted}'.format(
                      kind=kind, **stats))
        else:
            print('  Inserted {inserted} new {kind} (new total: {total}), '
                  'updated {updated}, superfluous {superfluous}'.format(
                      kind=kind, **stats))
        if stats['details']:
            print("  Details:\n    %s" % "\n    ".join(stats['details']))
        const.commit()

    print("Inserting code values.")
    # TODO: Generalize the two following lines
    for kind in ('Constants', 'CLConstants'):
        do(kind)


def clean_codes_from_change_log(db):
    """ Deletes entries in change_log referencing a deleted change type. """
    co = Factory.get('CLConstants')()
    codes = [x for x in co._get_superfluous_codes()
             if x[0] is co.ChangeType]
    for cls, code, name in codes:
        print('Found superfluous change type: {}'.format((cls, code, name)))
        num_entries = db.query_1(
            "SELECT count(*) FROM change_log "
            "WHERE change_type_id = {}".format(code))
        print('{} has {} change log entries'.format(name, num_entries))
        if num_entries:
            print('Deleting changes of type {}'.format(name))
            db.execute(
                "DELETE FROM change_log "
                "WHERE change_type_id = {}".format(code))
    print('Committing...')
    db.commit()
    print('Done.')


def make_inital_users(db):
    print("Creating initial entities.")
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
    a.populate(
        name=cereconf.INITIAL_ACCOUNTNAME,
        owner_type=co.entity_group,
        owner_id=eg.entity_id,
        np_type=int(co.account_program),
        creator_id=ea.entity_id,
        expire_date=None,
        description=None,
        parent=ea,
    )
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
    g.populate(
        creator_id=a.entity_id,
        visibility=co.group_visibility_all,
        name=cereconf.INITIAL_GROUPNAME,
        group_type=co.group_type_internal,
        parent=eg)
    g.write_db()
    g.add_member(a.entity_id)
    db.commit()


def check_schema_versions(db, strict=False):
    modules = {
        'ad': 'Cerebrum.modules.ADObject',
        'ad_email': 'Cerebrum.modules.no.uit.ad_email',
        'apikeys': 'Cerebrum.modules.apikeys',
        'auditlog': 'Cerebrum.modules.audit',
        'bofhd_requests': 'Cerebrum.modules.bofhd_requests.request',
        'changelog': 'Cerebrum.modules.ChangeLog',
        'disk_quota': 'Cerebrum.modules.disk_quota',
        'dns': 'Cerebrum.modules.dns',
        'email': 'Cerebrum.modules.Email',
        'entity_expire': 'Cerebrum.modules.entity_expire',
        'entity_trait': 'Cerebrum.modules.EntityTrait',
        'eventlog': 'Cerebrum.modules.EventLog',
        'events': 'Cerebrum.modules.event_publisher',
        'hostpolicy': 'Cerebrum.modules.hostpolicy',
        'legacy_users': 'Cerebrum.modules.legacy_users',
        'note': 'Cerebrum.modules.Note',
        'password_history': 'Cerebrum.modules.pwcheck.history',
        'posixuser': 'Cerebrum.modules.PosixUser',
        'stedkode': 'Cerebrum.modules.no.Stedkode',
        'stillingskoder': 'Cerebrum.modules.no.stillingskoder',
        'consent': 'Cerebrum.modules.consent.Consent',
        'employment': 'Cerebrum.modules.no.PersonEmployment',
        'gpg': 'Cerebrum.modules.gpg',
    }
    meta = Metainfo.Metainfo(db)
    for name, value in meta.list():
        if isinstance(value, tuple):
            print("WARNING: The version number of module {modulename} is "
                  "saved as a tuple.".format(modulename=name))
            value = "%d.%d.%d" % value
        if name == Metainfo.SCHEMA_VERSION_KEY:
            if not Cerebrum.__version__ == value:
                print("WARNING: cerebrum version %s does not"
                      " match schema version %s" % (
                          Cerebrum.__version__,
                          value))
                if strict:
                    exit(1)
        elif name.startswith('sqlmodule_'):
            name = name[len('sqlmodule_'):]
            if name not in modules:
                # print "WARNING: unknown module %s" % name
                # if strict: exit(1)
                continue
            try:
                module = dyn_import(modules[name])
                version = module.__version__
            except Exception as e:
                print("ERROR: can't find version of module %s: %s" %
                      (name, e))
                continue
            if not version == value:
                print("WARNING: module %s version %s does"
                      " not match schema version %s" %
                      (name, version, value))
                if strict:
                    exit(1)
        else:
            print("ERROR: unknown metainfo %s: %s" %
                  (name, value))
            if strict:
                exit(1)


def get_filelist(db, extra_files=None):
    if extra_files is None:
        extra_files = []
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
    """Execute an SQL definition file.

    @type fname: str
    @param fname:
        The file path for the given SQL definition file.

    @type db: Cerebrum.database.Database
    @param db:
        The Cerebrum database object, used for communicating with the db.

    @type debug: int
    @param debug:
        Sets how much debug information that should be printed out, e.g.
        traceback of errors.

    @type phase: str
    @param phase:
        What phase/category/stage that should be executed. This is used to
        decide what should be executed from the SQL file.

    """
    global all_ok
    print("Reading file (phase=%s): <%s>" % (phase, fname))
    statements = list(sql_parser.parse_sql_file(fname))

    output_col = None
    max_col = 78
    metainfo = {}
    for _, for_phase, for_rdbms, stmt in sql_parser.categorize(statements):
        if for_phase == sql_parser.PHASE_METAINFO:
            key, value = sql_parser.parse_metainfo(stmt)
            metainfo[key] = value
            continue

        if for_phase != phase:
            continue

        if (for_rdbms is not None and for_rdbms != db.rdbms_id):
            continue

        try:
            status = "."
            try:
                db.execute(stmt)
            except db.DatabaseError as e:
                all_ok = False
                status = "E"
                print("\n  ERROR: [%s]" % stmt)
                print(e)
                if debug:
                    print("  Database error: ", end="")
                    if debug >= 2:
                        # Re-raise error, causing us to (at least)
                        # break out of this for loop.
                        raise
                    else:
                        traceback.print_exc(file=sys.stdout)
            except Exception as e:
                all_ok = False
                status = "E"
                print("\n  ERROR: [%s]" % (stmt,))
                print(e)
                traceback.print_exc(file=sys.stdout)
                raise
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

            # TODO: Why commit after each statement? Wouldn't it be better to
            # execute statements, and do rollback on failures? This just causes
            # us to end up in a broken state if anything goes wrong...
            db.commit()

    if phase in {sql_parser.PHASE_MAIN,
                 sql_parser.PHASE_METAINFO,
                 sql_parser.PHASE_DROP}:
        # Update metainfo
        meta = Metainfo.Metainfo(db)
        if metainfo['name'] == 'core':
            name = Metainfo.SCHEMA_VERSION_KEY
            # tuple, for some reason?
            version = metainfo['version'].version
        else:
            name = 'sqlmodule_%s' % metainfo['name']
            version = str(metainfo['version'])
        if phase == 'drop':
            meta.del_metainfo(name)
        else:
            meta.set_metainfo(name, version)
        db.commit()

    if output_col is not None:
        print("")



if __name__ == '__main__':
    main()
