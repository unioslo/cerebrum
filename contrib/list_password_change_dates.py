#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2023 University of Oslo, Norway
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
Takes a file with account names, lists password change timestamps.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistory
from Cerebrum.utils import date_compat


logger = logging.getLogger(__name__)


def read_account_names(filename):
    """ Read account names from file. """
    with open(filename) as f:
        for lineno, line in enumerate(f, 1):
            account_name = line.rstrip()
            if not account_name:
                continue
            yield account_name


def get_last_ts(db, entity_id):
    """ Get most recent password change date for a given entity_id. """
    ph = PasswordHistory(db)
    last_ts = None
    for row in ph.get_history(entity_id):
        ts = date_compat.get_datetime_naive(row['set_at'])
        if not last_ts or ts and ts > last_ts:
            last_ts = ts
            continue
    return last_ts


def print_change_dates(accounts):
    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)

    for account_name in accounts:
        ac.clear()

        try:
            ac.find_by_name(account_name)
        except Errors.NotFoundError:
            logger.error("No such account: %s", repr(account_name))
            continue

        last_ts = get_last_ts(db, ac.entity_id)
        date_str = str(last_ts) if last_ts else 'NEVER'
        print("{}\t{}".format(account_name, date_str))


def main(inargs=None):
    """ Script invocation. """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-a', '--account-file',
        dest='account_file',
        help='text file with newline separated account names',
        required=True,
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf("console", args)

    accounts = read_account_names(args.account_file)
    print_change_dates(accounts)


if __name__ == '__main__':
    main()
