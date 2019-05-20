#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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

"""This script overrides display name for a list of users from the portal."""

from __future__ import unicode_literals

import io
import logging
import requests
import argparse
import os
import mx
import re

import cereconf
import Cerebrum.logutils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args


SCRIPT_NAME = __file__.split("/")[-1]
TODAY = mx.DateTime.today().strftime("%Y-%m-%d")
URL = 'http://jep2n1.uit.no:7080/navnealias'
DEFAULT_FILENAME = 'name_updates_%s.csv' % (TODAY,)
DEFAULT_OUTFILE = os.path.join(cereconf.DUMPDIR, 'name_updates',
                               DEFAULT_FILENAME)

logger = logging.getLogger(__name__)


def get_changes(url):
    """ Get name updates from Portal HTML """
    changes = {}
    invalid_chars = re.compile('[,;"=\+\\\\<>]')

    logger.info("Requesting changelog HTML page from Portal")
    response = requests.get(url)
    text = response.text

    logger.info("Going through lines in changelog")
    for line in text.split('\n'):
        username = None
        first_name = None
        last_name = None

        # Parse each line
        aux = line.split(';')
        if len(aux) == 4:
            username = aux[0].strip()
            first_name = aux[1].strip()
            last_name = aux[2].strip()
        elif len(aux) > 4:
            logger.error("Illegal use of semicolon! Line: %s.", line)
            continue

        # Check for repeated usernames
        if username in changes:
            logger.warn(
                "Repeated username in changelog. Only last entry is "
                "considered! Username: %s.", username)

        if username and first_name and last_name:
            if len(invalid_chars.findall(first_name)) > 0 or len(
                    invalid_chars.findall(last_name)):
                logger.error(
                    "Skipped line because of invalid characters. Username: %s."
                    " Firstname: %s. Lastname %s.",
                        username, first_name, last_name)
            else:
                changes[username] = (first_name, last_name)
        else:
            logger.info(
                "Skipped line because of missing data. Username: %s. "
                "Firstname: %s. Lastname %s.",
                    username, first_name, last_name)

    return changes


def change_names(changes, outfile, const, account, person, db):
    """ Change names in Cerebrum (if different from Portal HTML) """
    fp = io.open(outfile, 'w', encoding="utf-8")
    fp.write(
        '#username,old_first_name,new_first_name,old_last_name,new_last_name\n'
    )

    logger.info("Creating dict person_id -> cached names")
    registered_changes = 0
    cached_names = person.getdict_persons_names(
        source_system=const.system_cached,
        name_types=(const.name_first, const.name_last))

    logger.info("Creating dict username -> owner_id")
    cached_acc2owner = {}
    acc_list = account.search(expire_start=None)
    for acc in acc_list:
        cached_acc2owner[acc['name']] = acc['owner_id']

    logger.info("Processing list of potential name changes")
    for account_name in changes:

        if '999' in account_name:
            logger.warning(
                "Found administrative account %s. Skipping!", account_name)
            continue

        (firstname, lastname) = changes[account_name]
        fullname = ' '.join((firstname, lastname))

        # Find the account owner in dict
        owner = cached_acc2owner.get(account_name, None)
        if owner:

            # Look up cached names for given owner
            cached_name = cached_names.get(owner, None)
            if cached_name:

                # Override name if names differ
                if firstname != cached_name.get(
                        int(const.name_first)) or lastname != cached_name.get(
                        int(const.name_last)):

                    account.clear()
                    person.clear()

                    try:
                        account.find_by_name(account_name)
                    except Errors.NotFoundError:
                        logger.error(
                            "Account %s not found, cannot set new display"
                            " name", account_name)
                        continue

                    try:
                        person.find(account.owner_id)
                    except Errors.NotFoundError:
                        logger.error(
                            "Account %s owner %d not found, cannot set new "
                            "display name", account, account.owner_id)
                        continue

                    source_system = const.system_override
                    person.affect_names(source_system,
                                        const.name_first,
                                        const.name_last,
                                        const.name_full)
                    person.populate_name(const.name_first, firstname)
                    person.populate_name(const.name_last, lastname)
                    person.populate_name(const.name_full, fullname)

                    try:
                        person.write_db()
                    except db.DatabaseError, m:
                        logger.error(
                            "Database error, override names not updated for"
                            " %s: %s", account_name, m)
                        continue

                    person._update_cached_names()
                    try:
                        person.write_db()
                    except db.DatabaseError, m:
                        logger.error(
                            "Database error, cached name not updated for"
                            " %s: %s", account_name, m)
                        continue

                    logger.info(
                        "Name changed for user %s. "
                        "First name: \"%s\" -> \"%s\". "
                        "Last name: \"%s\" -> \"%s\".",
                            account_name,
                            cached_name.get(int(const.name_first)),
                            firstname,
                            cached_name.get(int(const.name_last)),
                            lastname
                    )
                    fp.write('%s,%s,%s,%s,%s\n' % (
                        account_name,
                        cached_name.get(int(const.name_first)),
                        firstname,
                        cached_name.get(int(const.name_last)),
                        lastname))
                    registered_changes = registered_changes + 1

                # Do nothing if names are equal
                else:
                    continue

            else:
                logger.error(
                    "Cached names for %s not found in dict, cannot set new "
                    "display name", account_name)
                continue

        else:
            logger.warn(
                "Account %s not found in dict, cannot set new display name",
                    account_name)
            continue

    logger.info("Registered %s changes", registered_changes)
    fp.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--outfile',
        default=DEFAULT_OUTFILE
    )
    parser.add_argument(
        '-t', '--test-data',
        help='Use test data',
        action='store_true',
    )
    add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf(cereconf.DEFAULT_LOGGER_TARGET, args)

    if args.test_data:
        logger.info('Running script with test data')
        changes = {'rmi000': ('Romulus', 'Mikalsen'),
                   'bto001': ('Bjarne', 'Betjent')}
    else:
        changes = get_changes(URL)

    db = Factory.get('Database')()
    db.cl_init(change_program=SCRIPT_NAME)
    const = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    change_names(changes, args.outfile, const, account, person, db)

    if args.commit:
        db.commit()
        logger.info("Committed changes to DB")
    else:
        db.rollback()
        logger.info("Dryrun, rollback changes")


if __name__ == '__main__':
    main()
