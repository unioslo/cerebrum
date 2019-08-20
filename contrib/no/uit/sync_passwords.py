#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Tromso, Norway
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
This script checks if password hashes are the same in the old and new
Cerebrum databases (old on Caesar, new on Clavius).  If they differ
the hashes on Caesar are copied to Clavius.
"""

import argparse
import logging
import os

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit.account_bridge import AccountBridge
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


def sync_one_account(db, bridge, uname):
    """
    Sync passwords for a single account.

    :param db: A database connection to sync to
    :param bridge: An AccountBridge object to sync from
    :param uname: A username to sync
    """
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    auth_data = bridge.get_auth_data(uname)
    if auth_data is None:
        logger.warning("No account with username=%r on Caesar, ignoring",
                       uname)
        return

    # get auth data from new database
    ac.clear()
    ac.find_by_name(uname)

    first = True
    equal = True
    # compare auth data from the two databases, logg if differences
    for ad in auth_data:
        auth_method, caesar_data = ad
        auth_method = co.Authentication(auth_method)

        # don't compare auth_data for auth methods that aren't in use
        if str(auth_method) not in cereconf.AUTH_CRYPT_METHODS:
            continue

        try:
            clavius_data = ac.get_account_authentication(auth_method)
        except Errors.NotFoundError:
            # this authentication method is not in clavius db for this account,
            # ignore it
            continue

        if caesar_data != clavius_data:
            if first:
                logger.debug("CHANGE: username=%r has auth_data that differs",
                             uname)
                first = False
                equal = False

            logger.debug("username=%r, type=%s, caesar=%r, clavius=%r",
                         uname, auth_method, caesar_data, clavius_data)
    if not equal:
        logger.debug("NO CHANGE: username=%r has no changes")

    # Note: all auth_data from Caesar is written to Clavius, regardless of what
    # type it is.

    # update auth_data in Clavius database with auth_data from Caesar
    ac.set_auth_data(auth_data)
    ac.write_db()


def sync_many(db, bridge, usernames):
    for username in usernames:
        sync_one_account(db, bridge, username)


def read_usernames(filename):
    """Read usernames from file."""
    logger.info("Reading usernames from %r", filename)
    count = 0
    with open(filename, 'r') as f:
        for line in f:
            username = line.strip()
            if username:
                count += 1
                yield username
    logger.info("Read %d usernames from %r", count, filename)


def fetch_usernames(db):
    """Fetch usernames from database."""
    logger.info("Reading usernames from db")
    ac = Factory.get('Account')(db)
    count = 0
    for row in ac.list_all(filter_expired=False):
        count += 1
        yield row['entity_name']
    logger.info("Read %d usernames from db", count)


def existing_file(filename):
    if not os.path.exists(filename):
        raise ValueError("File %r seems to be missing" % (filename, ))
    return filename


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Sync passwords from Caesar to current database",
    )
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help='Sync all users in current database',
    )
    what.add_argument(
        '-f', '--file',
        dest='filename',
        type=existing_file,
        help='Sync usernames from file %(metavar)s',
        metavar='FILE',
    )
    what.add_argument(
        '-n', '--name',
        dest='username',
        help='Sync a single username %(metavar)s',
        metavar='USER',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='sync_passwords')

    with AccountBridge() as bridge:
        if args.username:
            sync_one_account(bridge, args.username)
        elif args.filename:
            sync_many(db, bridge, read_usernames(args.filename))
        elif args.all:
            sync_many(db, bridge, fetch_usernames(db))

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        db.rollback()
        logger.info('Rolling back changes')

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
