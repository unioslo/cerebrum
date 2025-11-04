#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2025 University of Oslo, Norway
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

This script is the main tool for managing Cerebrum's postgres database.  It
supports creating and updating the required tables and Cerebrum constants.

Database files
--------------
The database structure for Cerebrum and optional modules are defined as
`sql_parser` files in `design/*.sql`.  Cerebrum uses a custom SQL file format,
defined in :mod:`Cerebrum.database.sql_parser`.  These files are *mostly*
standard SQL, but statements are classified into *phases*.

Use cases
---------
Insert/update constants
    Whenever a new constant is defined in the soure code, it also needs to be
    inserted into a constants code table.

    Run: ``makedb.py --only-insert-codes``

    This is a fairly routine task, and is commonly done as a final step during
    code deployment.

    Note: Update typically won't work in practice, as there are usually
    existing data and constraints that prevents constants from being deleted.

Add/remove database "modules"
    Optional Cerebrum features may depend on optional database tables.
    Whenever one of these features are added or removed, the associated
    database structures must be added or removed as well.

    Run: ``makedb.py [--drop] <design/mod_foo.sql>``

    This happens infrequently throughout the lifetime of a
    database/environment.

Setting up a new database
    Whenever a completely new, distinct environment is being set up, it will
    need its own database.

    Run: ``makedb.py [--extra-file design/mod_foo.sql]...``

    This happens exactly once per database/environment.  Optional, initial
    modules can be included with `--extra-file`.

Creating initial entities
    Most Cerebrum features depend on some initial database entities (e.g.
    ``INITIAL_ACCOUNTNAME``, ``INITIAL_GROUPNAME``).  Whenever a new Cerebrum
    database is initialized, these entities must be created.

    This happens exactly once per database/environment.  It is automatically
    done after setting up a new database, but it can be repeated/forced with:
    ``makedb.py --force-bootstrap``

    Note: `CLASS_CHANGELOG` should be empty when running these operations.

Migrations
------------
The SQL files used to define and create database structures has no built-in
mechanisms for running migrations if the schema is modified.  Every database
update requires its own set of migration instructions.  These are defined in
``migrate-cerebrum-database.py``, and typically consists of:

1. A migration function that defines the overall migration
2. Optional `sql_parser` migration files for altering the schema, with
   statements typically categorized into pre/post phases.
3. Optional functions or scripts that processes and migrates data *between* the
   pre/post phases.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import os
import sys
import textwrap

import cereconf
import Cerebrum
import Cerebrum.logutils
from Cerebrum import Metainfo
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.database import sql_parser
from Cerebrum.utils.module import import_item

# TODO: This script should probably be split up into multiple scripts.
#
# 1. Insert is a fairly routine task, which is combined with some potentially
#    pretty descructive actions (like dropping db-schemas).  The *default*
#    action is to insert the common database tables...
#
# 2. Adding a single module vs setting up an initial database use different
#    arguments to specify optional modules (positional vs --extra-file option).
#    Again, the default is to set up the initial database tables, but
#    adding/removing modules is a more common use case.
#
# 3. Creating initial accounts is a one-time action, and requries specific
#    config (i.e. no Changelog/auditlog).  We should probably have scripts to
#    create other, internal entities as well (e.g. BOFHD_SUPERUSERS).  Also, we
#    should probably have some workaround for creating entities without a
#    changelog.

logger = logging.getLogger(__name__)
log_format = "%(levelname)s: %(message)s"
log_level = logging.INFO

# Add a 'mock phase' for inserting new constants (equivalent to
# --only-insert-codes).  By having two leading spaces in the value, we ensure
# it won't conflict with actual `sql_parser` phases.  This safeguard works
# because runfile() will collapse any sequence of whitespace into a single
# space.
PHASE_INSERT = "  insert"

# Default order of operations
DEFAULT_PHASE_ORDER = (
    sql_parser.PHASE_CODE,
    PHASE_INSERT,
    sql_parser.PHASE_MAIN,
)


parser = argparse.ArgumentParser(
    description=textwrap.dedent(
        "Create or delete database schemas, or update constants."
    ),
    epilog=textwrap.dedent(
        """
        Update constants
            Typically done after deploying code changes:

            python makedb.py --only-insert-codes

        Update schema
            Add a new database module, or remove an obsolete one:

            python makedb.py [--drop] <sql-file>

        Create schema
            Initial setup of a new database:

            python makedb.py [--extra-file <sql-file>]...

        WARNING: `makedb.py` can be very destructive!  Make sure to test any
        command thoroughly before running in production!

        See `contrib/migrate/migrate-cerebrum-database.py` for migrating
        existing schemas.
        """
    ).strip(),
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
const_mutex = parser.add_mutually_exclusive_group()
const_mutex.add_argument(
    "--only-insert-codes",
    action="store_const",
    const="insert",
    dest="const_action",
    help=(
        """
        Insert or update constants defined in `cereconf.CLASS_CONSTANTS`.
        Note: Will not create constant tables.
        """
    ),
)
const_mutex.add_argument(
    "--update-codes",
    action="store_const",
    const="update",
    dest="const_action",
    help=(
        """
        Like --update-codes, but remove any constant from the database that
        aren't defined in `cereconf.CLASS_CONSTANTS`.
        Note that this will usually cause problems with FKs, and should
        generally not be used.
        See cerebrum-hacks for helpers to remove truly obsolete or broken
        constants.
        """
    ),
)

parser.add_argument(
    "--extra-file",
    action="append",
    help=(
        """
        For each phase, run statements for core cerebrum, then each
        %(metavar)s.  This option can be repeated:  For each phase, the
        additional %(metavar)ss wil run in the order they are given.

        This is *only* used when setting up an initial database.
        """
    ),
    metavar="SQL-FILE",
)

stage_mutex = parser.add_mutually_exclusive_group()
stage_mutex.add_argument(
    "--drop",
    action="store_const",
    const=sql_parser.PHASE_DROP,
    dest="stage",
    help=(
        """
        Perform only the 'drop' phase of any SQL files.  WARNING: This will
        remove tables and the data they're holding from your database.
        """
    ),
)
stage_mutex.add_argument(
    "--stage",
    choices=(sql_parser.PHASE_CODE, sql_parser.PHASE_MAIN),
    dest="stage",
    help="Perform only the %(metavar)s phase of any SQL files.",
    metavar="STAGE",
)
parser.add_argument(
    "-f", "--force-bootstrap",
    action="store_true",
    dest="bootstrap",
    help=(
        """
        Perform the bootstrap phase only (create initial objects).
        Requires an up-to-date database schema.
        Does not work well if the audit log is included in
        `cerebrum.CLASS_CHANGELOG`.
        """
    ),
)
parser.add_argument(
    "module",
    nargs="*",
    help="An sql module to add to or remove from the current schema",
)


def get_db_user():
    """ Get db-user from cereconf. """
    # Not sure why we do this at all - the `table_owner` stuff is really for
    # Oracle, should probably drop this setting.
    username = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('table_owner')
    if not username:
        username = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if username:
            logger.debug(
                "No CEREBRUM_DATABASE_CONNECT_DATA['table_owner'], "
                "falling back to regular 'user' (%s)", username,
            )
    return username


def main(argv=None):
    args = parser.parse_args(argv)
    db = Factory.get('Database')(user=get_db_user())
    db.cl_init(change_program="makedb", change_by=cereconf.INITIAL_ACCOUNT_ID)
    # Monkeypatch constants to use our current db-transaction:
    _CerebrumCode.sql = property(lambda *propargs: db)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    #
    # Standalone non-schema actions:
    #

    # --force-bootstrap
    if args.bootstrap:
        logger.debug("Running manual bootstrap and exiting...")
        check_schema_versions(db)
        make_inital_users(db)
        db.commit()
        return 0

    # --only-insert-codes
    if args.const_action == "insert":
        logger.debug("Inserting codes and exiting...")
        insert_code_values(db, delete_extra_codes=False, print_details=True)
        check_schema_versions(db)
        return 0

    # --update-codes
    if args.const_action == "update":
        logger.debug("Updating codes and exiting...")
        insert_code_values(db, delete_extra_codes=True, print_details=True)
        check_schema_versions(db)
        return 0

    #
    # Schema changes
    #

    if args.module:
        # only process selected sql files (modules)
        do_bootstrap = False
        files = args.module
        logger.debug("processing module files: %s", repr(files))
    else:
        # process core schema + extra-files
        do_bootstrap = True
        files = get_filelist(db, args.extra_file or [])
        logger.debug("processing main schema with files: %s", repr(files))

    # success hint - if any statement "soft" fails in any file, this will be
    # False, and `main()` returns 1
    all_ok = True

    # --drop
    if args.stage == sql_parser.PHASE_DROP:
        # With --drop, all we should do is run the 'drop' category
        # statements.  Reverse the SQL file order to drop modules
        # depending on core first; statement order in each file is NOT
        # reversed,  though.
        all_ok = True
        for filename in reversed(files):
            all_ok = runfile(filename, db, sql_parser.PHASE_DROP) and all_ok
        return int(not all_ok)

    # Regular non-drop schema update
    if args.stage:
        # ... but only with the "code" or "main" phase
        # Not sure how useful this is in practice - may want to remove this
        # option?
        order = (args.stage,)
    else:
        order = DEFAULT_PHASE_ORDER

    for phase in order:
        if phase == PHASE_INSERT:
            # A mock phase to ensure missing codes are present
            insert_code_values(db, delete_extra_codes=False,
                               print_details=False)
            continue
        for filename in files:
            all_ok = runfile(filename, db, phase) and all_ok

    if do_bootstrap:
        # When bootstrapping, make sure the versions match
        check_schema_versions(db, strict=True)
        make_inital_users(db)
        db.commit()
    else:
        check_schema_versions(db)

    return int(not all_ok)


def insert_code_values(db, delete_extra_codes=False, print_details=False):

    def details_sort_key(value):
        # key function to sort inserts and updates before superfluous codes in
        # detailed output
        categories = ["Inserted", "Updated", "Superfluous"]
        weight = len(categories)
        category = value.partition(" ")[0]
        if category in categories:
            weight = categories.index(category)
        return (weight, value)

    def do(kind):
        logger.debug("Inserting %s code values...", kind)
        const = Factory.get(kind)(db)
        try:
            stats = const.initialize(delete=delete_extra_codes)
        except db.DatabaseError:
            attr_hint = (
                "CLASS_CL_CONSTANTS"
                if kind == "CLConstants"
                else "CLASS_CONSTANTS"
            )
            logger.error("Unable to initialize constants (check cereconf.%s)",
                         attr_hint)
            raise

        if delete_extra_codes:
            logger.info("Inserted %d new %s (new total: %d), updated: %d, "
                        "deleted: %d",
                        stats['inserted'], kind, stats['total'],
                        stats['updated'], stats['deleted'])
        else:
            logger.info("Inserted %d new %s (new total: %d), updated: %d",
                        stats['inserted'], kind, stats['total'],
                        stats['updated'])

        if print_details and stats['details']:
            print("Details:\n  %s" % "\n  ".join(sorted(stats['details'],
                                                        key=details_sort_key)))
        const.commit()

    # TODO: Generalize the two following lines
    for kind in ('Constants', 'CLConstants'):
        do(kind)


def make_inital_users(db):
    logger.info("Creating initial entities...")
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


#
# Schema version checks
#

# Map sql module name to python module name
MODULES = {
    'ad_attributes': 'Cerebrum.modules.ad_attributes',
    'apikeys': 'Cerebrum.modules.apikeys',
    'auditlog': 'Cerebrum.modules.audit',
    'bofhd_requests': 'Cerebrum.modules.bofhd_requests',
    'changelog': 'Cerebrum.modules.ChangeLog',
    'disk_quota': 'Cerebrum.modules.disk_quota',
    'email': 'Cerebrum.modules.Email',
    'entity_trait': 'Cerebrum.modules.trait',
    'eventlog': 'Cerebrum.modules.EventLog',
    'events': 'Cerebrum.modules.event_publisher',
    'job_runner': 'Cerebrum.modules.job_runner',
    'otp': 'Cerebrum.modules.otp',
    'note': 'Cerebrum.modules.Note',
    'password_history': 'Cerebrum.modules.pwcheck.history',
    'posixuser': 'Cerebrum.modules.PosixUser',
    'stedkode': 'Cerebrum.modules.no.Stedkode',
    'consent': 'Cerebrum.modules.consent.Consent',
    'employment': 'Cerebrum.modules.no.PersonEmployment',
    'gpg': 'Cerebrum.modules.gpg',
    'task_queue': 'Cerebrum.modules.tasks',
}


def get_module_version(name):
    """ Get python module version for a known sql module mapping. """
    if name not in MODULES:
        # Should this be a warning?
        logger.debug("Missing source code version for: %s", repr(name))
        return None

    module_name = MODULES[name]
    try:
        module = import_item(module_name)
        version = module.__version__
        logger.debug("found module version for %s: %s",
                     repr(module_name), repr(version))
        return version
    except Exception as e:
        logger.warning("can't get module version for %s (%s)",
                       repr(module_name), e)
    return None


def check_schema_versions(db, strict=False):
    """
    Check database schema version against python module version.

    :param bool strict:
        Raise an exception on version mismatch.

        Default: False - only log a warning if there is a mismatch or a problem
        comparing version numbers.
    """
    meta = Metainfo.Metainfo(db)
    for name, value in meta.list():
        # Legacy work-around for different version types:
        if isinstance(value, tuple):
            logger.warning(
                "Invalid version in module %s (expected str, got tuple)",
                repr(name),
            )
            value = "%d.%d.%d" % value

        if name == Metainfo.SCHEMA_VERSION_KEY:
            if not Cerebrum.__version__ == value:
                logger.warning(
                    "cerebrum version %s doesn't match schema version %s",
                    Cerebrum.__version__, value,
                )
                if strict:
                    raise RuntimeError("Version mismatch for module: "
                                       + repr(Metainfo.SCHEMA_VERSION_KEY))
        elif name.startswith('sqlmodule_'):
            name = name[len('sqlmodule_'):]
            if name == Metainfo.SCHEMA_VERSION_KEY:
                # An old bug workaround
                continue
            version = get_module_version(name)
            if version is None:
                continue
            if not version == value:
                logger.warning(
                    "module %s version %s doesn't match schema version %s",
                    name, version, value,
                )
                if strict:
                    raise RuntimeError("Version mismatch for module: "
                                       + repr(name))
        else:
            logger.error("Unknown metainfo: %s, %s", name, value)
            if strict:
                raise RuntimeError("Unknown metainfo: %s, %s"
                                   % (name, value))


def get_filelist(db, extra_files=None):
    """ Get files to execute for setting up a new database. """
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


def runfile(fname, db, phase):
    """
    Execute statements from a `sql_parser` compatible SQL file.

    :param str fname: Path to a file to run
    :param db: A database connection/transaction to run the statements in
    :param str phase: A phase to execute from the file.
    """
    runfile_ok = True
    logger.info("Reading file %s (phase=%s)", repr(fname), repr(phase))
    statements = list(sql_parser.parse_sql_file(fname))

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

        logger.debug("running statement: %s", stmt)
        # Maybe drop the `.` and `E` progress chars, and log individual
        # statements and their result?  Not sure if we really need to save on
        # output here.  Any error will be interrupted by a traceback anyway?
        try:
            success = True
            try:
                db.execute(stmt)
            except db.DatabaseError:
                # This will mostly be 'foo already  exists', 'foo does not
                # exist' - often due to incorrect `fname` (e.g. dropping a
                # database module that has already been dropped)
                runfile_ok = success = False
                logger.error("Database error in: %s", stmt, exc_info=True)
            except Exception:
                # A generic error will usually be actual errors in the sql
                # file, or incorrect `fname` (ordering/missing dependencies).
                # We can't really recover here, so we re-raise the error and
                # fail hard.
                runfile_ok = success = False
                # No need to log trace (exc_info), as we reraise
                logger.error("Unknown error in: %s", stmt)
                raise
        finally:
            if success:
                logger.debug("Statement OK: %s", stmt)
            else:
                logger.error("Statement Failed: %s", stmt)

            # TODO: Why commit after each statement? Wouldn't it be better to
            # execute statements, and do rollback on failures? This just causes
            # us to end up in a broken state if anything goes wrong...
            db.commit()

    if phase in (sql_parser.PHASE_MAIN,
                 sql_parser.PHASE_METAINFO,
                 sql_parser.PHASE_DROP):
        # Update metainfo
        meta = Metainfo.Metainfo(db)
        if metainfo['name'] == 'core':
            name = Metainfo.SCHEMA_VERSION_KEY
            # tuple, for some reason?
            version = metainfo['version'].version
        else:
            name = 'sqlmodule_%s' % metainfo['name']
            version = str(metainfo['version'])
        if phase == sql_parser.PHASE_DROP:
            meta.del_metainfo(name)
        else:
            meta.set_metainfo(name, version)
        db.commit()

    if runfile_ok:
        logger.debug("runfile(%s, <db>, %s) completed",
                     repr(fname), repr(phase))
    else:
        logger.warning("runfile(%s, <db>, %s) completed with errors",
                       repr(fname), repr(phase))
    return runfile_ok


def main_wrapper(argv=None):
    logging.basicConfig(format=log_format, level=log_level)
    errors = main(argv)
    if errors:
        logger.warning("makedb completed with errors")
    else:
        logger.info("makedb completed without errors")
    sys.exit(int(errors))


if __name__ == '__main__':
    main_wrapper()
