#!/usr/bin/env python2.2
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

import time
import getopt
import sys
import os

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import Account
from Cerebrum import Metainfo
from Cerebrum.Constants import _SpreadCode

# run migrate_* in this order
versions = ('rel_0_9_2', 'rel_0_9_3')

def makedb(release, stage):
    print "Running Makedb(%s, %s)..." % (release, stage)
    cmd = ['%s/makedb.py' % makedb_path, '--stage', stage,
           '%s/migrate_to_%s.sql' % (design_path, release)]
    r = os.system(" ".join(cmd))
    if r:
        continue_prompt("Exit value was %i, continue? (y/n)[y]" % r)
    if stage == 'pre':
        cmd = ['%s/makedb.py' % makedb_path, '--only-insert-codes']
        r = os.system(" ".join(cmd))
        if r:
            continue_prompt("Exit value was %i, continue? (y/n)[y]" % r)

def continue_prompt(message):
    print message
    r = sys.stdin.readline()
    if len(r) > 1 and r[0] != 'y':
        print "aborting"
        sys.exit(1)

def assert_db_version(wanted):
    meta = Metainfo.Metainfo(db)
    version = "pre-0.9.2"
    try:
        version = "%d.%d.%d" % meta.get_metainfo(Metainfo.SCHEMA_VERSION_KEY)
    except Errors.NotFoundError:
        pass
    except Exception, e:
        # Not sure how to trap the PgSQL OperationalError
        if str(e.__class__).find("OperationalError") == -1:
            raise
    if wanted <> version:
        print "your database is %s, not %s, aborting" % (version, wanted)
        sys.exit(1)

def migrate_to_rel_0_9_2():
    """Migrate a pre 0.9.2 (the first version) database to the 0.9.2
    database schema."""

    assert_db_version("pre-0.9.2")
    
    # TODO: Assert that the new classes has been installed
    makedb('0_9_2', 'pre')

    spreads = []
    for s in cereconf.HOME_SPREADS:
        spreads.append(str(getattr(co, s)))
    assert spreads

    # fill the account_home table for the relevant spreads

    # Normally, it is a no-no to use SQL outside the API.  However,
    # when migrating some data may not be available because the
    # installed API and the database are out of sync.
    ac = Account.Account(db)
    count = 0
    print "Populating account_home"
    processed = {}

    # Add an entry in account_home for each spread in HOME_SPREADS
    # that the account currently has a spread to
    for row in db.query(
        """SELECT account_id, home, disk_id, spread
        FROM [:table schema=cerebrum name=entity_spread] es,
             [:table schema=cerebrum name=account_info] ai
        WHERE es.entity_id=ai.account_id
        """, fetchall=False):
        spread = num2const[ int(row['spread']) ]
        if str(spread) in spreads:
            ac.clear()
            ac.find(row['account_id'])
            processed[int(row['account_id'])] = 1
            status = co.home_status_on_disk
            if ac.is_deleted():
                status = co.home_status_archived
            ac.set_home(spread, disk_id=row['disk_id'], home=row['home'],
                        status=status)
            ac.write_db()
            count += 1
            if (count % 100) == 1:
                sys.stdout.write('.')
                sys.stdout.flush()

    # Now include accounts not in HOME_SPREADS.  Their homedir is
    # bound to the first spread in HOME_SPREADS
    spread = str2const[spreads[0]]
    for row in db.query(
        """SELECT account_id, home, disk_id
        FROM [:table schema=cerebrum name=account_info]""", fetchall=False):
        if processed.has_key(int(row['account_id'])):
            continue
        ac.clear()
        ac.find(row['account_id'])
        status = co.home_status_on_disk
        if ac.is_deleted():
            status = co.home_status_archived
        ac.set_home(spread, disk_id=row['disk_id'], home=row['home'],
                    status=status)
        ac.write_db()
        count += 1
        if (count % 100) == 1:
            sys.stdout.write('.')
            sys.stdout.flush()
    print """
    NOTE: all entries added to account_home has status=on_disk unless
    account.is_deleted() returns True, which sets status to None"""

    db.commit()
    makedb('0_9_2', 'post')
    meta = Metainfo.Metainfo(db)
    meta.set_metainfo(Metainfo.SCHEMA_VERSION_KEY, (0,9,2))
    print "Migration to 0.9.2 completed successfully"
    db.commit()

def migrate_to_rel_0_9_3():
    """Migrate from 0.9.2 database to the 0.9.3 database schema."""

    assert_db_version("0.9.2")

    # TODO: Assert that the new classes has been installed
    makedb('0_9_3', 'pre')

    # Convert all rows in auth_op_target with has_attr true.  If
    # auth_op_target_attrs contains multiple rows, we need to add
    # additional rows.

    rows = db.query(
        """SELECT op_target_id, entity_id, target_type
        FROM [:table schema=cerebrum name=auth_op_target]
        WHERE has_attr=1""")
    print "%d rows to convert..." % len(rows)
    rows_per_dot = int(len(rows) / 79 + 1)
    count = 0
    for row in rows:
        if count % rows_per_dot == 0:
            sys.stdout.write('.')
            sys.stdout.flush()
        count += 1
        attr_rows = db.query(
            """SELECT attr
            FROM [:table schema=cerebrum name=auth_op_target_attrs]
            WHERE op_target_id=:id""", {'id': int(row['op_target_id'])})
        assert attr_rows
        db.execute(
            """UPDATE [:table schema=cerebrum name=auth_op_target]
            SET attr=:attr WHERE op_target_id=:id""",
            {'id': int(row['op_target_id']), 'attr': attr_rows[0]['attr']})
        for attr_row in attr_rows[1:]:
            values = {'op_target_id': int(db.nextval('entity_id_seq')),
                      'entity_id': int(row['entity_id']),
                      'target_type': row['target_type'],
                      'attr': attr_row['attr']}
            db.execute(
                """INSERT INTO [:table schema=cerebrum name=auth_op_target]
                (%(tcols)s)
                VALUES (%(tvalues)s)""",
                {'tcols': ", ".join([x[0] for x in values]),
                 'tvalues': ", ".join([x[1] for x in values])})
            # We need to duplicate the rows in auth_role which refer
            # to this op_target_id as well, but since our database
            # doesn't have multiple attr values, I won't bother to
            # implement it.  Let me know if you need it!
            raise NotImplementedError
    
    db.commit()
    print "\ndone."
    makedb('0_9_3', 'post')
    meta = Metainfo.Metainfo(db)
    meta.set_metainfo(Metainfo.SCHEMA_VERSION_KEY, (0,9,3))
    print "Migration to 0.9.3 completed successfully"
    db.commit()

def init():
    global db, co, str2const, num2const

    Factory = Utils.Factory
    db = Factory.get('Database')()
    db.cl_init(change_program="migrate")
    co = Factory.get('Constants')(db)

    str2const = {}
    num2const = {}
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _SpreadCode):
            str2const[str(tmp)] = tmp
            num2const[int(tmp)] = tmp

def main():
    global makedb_path, design_path
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'r',
                                   ['help', 'releases', 'from=', 'to=',
                                    'makedb-path=', 'design-path=',
                                    'no-changelog'])
    except getopt.GetoptError:
        usage(1)

    from_rel = to_rel = None
    makedb_path = design_path = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-r', '--releases',):
            print "\n".join(versions)
            sys.exit()
        elif opt in ('--makedb-path',):
            makedb_path = val
        elif opt in ('--design-path',):
            design_path = val
        elif opt in ('--no-changelog',):
            cereconf.CLASS_CHANGELOG = ('Cerebrum.ChangeLog/ChangeLog',)
        elif opt in ('--from',):
            from_rel = val
        elif opt in ('--to',):
            to_rel = val
        else:
            usage()
    if (not (from_rel or to_rel)) or (not (makedb_path and design_path)):
        usage()
        
    continue_prompt("Do you have a backup of your database? (y/n)[y]")
    init()
    started = False
    if not from_rel:
        started = True
    for v in versions:
        if not started:
            if from_rel == v:   # from is not inclusive
                started = True
        elif started:
            print "Running migrate_to_%s" % v
            globals()["migrate_to_%s" % v]()
            if to_rel == v:
                started = False

def usage(exitcode=0):
    # TBD: --from could be fetched from Metainfo, but do we want that?
    print """Usage: [options]
    Migrates database from one database-schema to another.
    --releases : list available release names
    --from release_name: migrate from this release
    --to release_name: migrate to this release
    --help: this text
    --makedb-path: directory where makedb.py is
    --design-path: directory where the sql files are
    --no-changelog: don't log the changes to the changelog
    
    If --from is omitted, all migrations up to --to is performed.  If
    --to is omitted, all migrations from --from is performed.

    --makedb-path and --design-path are mandatory
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
