#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2025 University of Oslo, Norway
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
Generate a list of primary accounts for persons with given affiliations.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


def get_primary_account_cache(db):
    ac = Factory.get('Account')(db)
    cache = {}
    logger.debug("caching primary accounts...")
    for row in ac.list_accounts_by_type(primary_only=True):
        person_id = row['person_id']
        account_id = row['account_id']
        cache[person_id] = account_id
    logger.info("Found %d primary accounts", len(cache))
    return cache


def get_account_name_cache(db):
    ac = Factory.get('Account')(db)
    cache = {}
    logger.debug("caching account names...")
    for row in ac.search():
        account_id = row['account_id']
        account_name = row['name']
        cache[account_id] = account_name
    logger.info("Found %d account names", len(cache))
    return cache


def find_person_ids_by_affiliation(db, affiliations):
    pe = Factory.get("Person")(db)
    co = Factory.get("Constants")(db)
    person_ids = set()
    for aff_string in affiliations:
        logger.info("Prosessing people with aff %s", repr(aff_string))
        aff, status = co.get_affiliation(aff_string)
        aff_repr = six.text_type(aff if status is None else status)
        new_ids = set(row['person_id']
                      for row in pe.list_affiliations(affiliation=aff,
                                                      status=status))
        logger.info("Found %d persons with aff '%s'", len(new_ids), aff_repr)
        person_ids.update(new_ids)
    logger.info("Found %d persons in total", len(person_ids))
    return person_ids


def get_accounts(db, affiliations):
    # Find persons with one of the the given affiliations
    person_ids = find_person_ids_by_affiliation(db, affiliations)

    # Cache account selection and details
    primary_accounts = get_primary_account_cache(db)
    account_names = get_account_name_cache(db)

    # ..then retrieve the primary accounty for each of them
    no_primary_account = 0
    no_name = 0
    all_accounts = set()
    for person_id in person_ids:
        primary_account_id = primary_accounts.get(person_id)
        if primary_account_id is None:
            logger.debug("no primary account for person id=%d", person_id)
            no_primary_account += 1
            continue

        name = account_names.get(primary_account_id)
        if name is None:
            logger.debug("no name for primary account id=%d (person id=%d)",
                         primary_account_id, person_id)
            no_name += 1
            continue

        all_accounts.add(name)

    logger.info("ignoring %d persons without primary accounts",
                no_primary_account)
    logger.info("ignoring %d primary accounts without name",
                no_name)
    logger.info("found %d primary accounts", len(all_accounts))
    return all_accounts


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="List primary accounts for persons with given affs.",
    )
    parser.add_argument(
        "-a", "--aff",
        dest="affiliations",
        action="append",
        help="an affiliation to include (can be repeated)",
    )
    parser.add_argument(
        "--students",
        action=argutils.ExtendConstAction,
        dest="affiliations",
        const=["STUDENT/aktiv", "STUDENT/drgrad", "STUDENT/evu"],
        help="add student affiliations: %(const)s",
    )
    parser.add_argument(
        "-f", "--file",
        dest="output",
        default="-",
        help="write report to %(metavar)s (default: stdout)",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)

    if not args.affiliations:
        parser.error(message="Must provide at least one affiliation")

    Cerebrum.logutils.autoconf("console", args)

    logger.info("Start: %s", parser.prog)
    db = Factory.get("Database")()

    with file_stream.get_output_context(args.output, encoding="utf-8") as f:
        sorted_accounts = sorted(get_accounts(db, args.affiliations))
        for account in sorted_accounts:
            f.write(account + "\n")

    logger.info("Done: %s", parser.prog)


if __name__ == "__main__":
    main()
