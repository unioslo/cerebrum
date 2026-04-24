#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2026 University of Oslo, Norway
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
This is an example script for Cerebrum.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


def get_account_by_id(db, account_id):
    ac = Factory.get('Account')(db)
    ac.find(int(account_id))
    return ac


def get_candidates(db):
    """Get personal user accounts without expire_date. """
    ac = Factory.get('Account')(db)
    seen = 0
    for a in ac.search(owner_type=ac.const.entity_person):
        seen += 1
        if not a['expire_date']:
            account = get_account_by_id(db, a['account_id'])
            yield (account, seen)


def get_new_expire_date(account, default=None, _today=None):
    """Get a new expire date for an account.

    :type account: Cerebrum.Account.Account
    :param account:
        The account to calculate expire date for.

    :type default: datetime.date
    :param default:
        The fallback value if no new expire date is found.
    """
    # The _today parameter can be useful in tests, but shouldn't normally
    # be used.
    today = _today or datetime.date.today()
    lifetime = today - date_compat.get_date(account.created_at)
    if lifetime == abs(lifetime):
        return today + lifetime
    return default


def set_new_expire_date(account, expire_date):
    """Sets a new expire date for all candidates."""
    account.expire_date = expire_date
    account.write_db()
    logger.debug("Set new expire date for %s: %s",
                 account.account_name,
                 account.expire_date)


def update_expire_dates(db):
    updates = []
    for account in get_candidates(db):
        expire_date = get_new_expire_date(account)
        set_new_expire_date(account, expire_date)
        updates.append((account.account_name, expire_date))
    logger.info("Updated expire date on %d accounts", len(updates))
    return updates


def write_report(filename, updates):
    with file_stream.get_outuput_context(filename, encoding="utf-8") as f:
        for username, expire_date in updates:
            line = "{}:{}".format(username, expire_date.isoformat())
            print(line, file=f)
    logger.info("Wrote report to %s", filename)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "-f", "--file",
        dest="fname",
        required=True,
        metavar="<filename>",
        help="Write export data to <filename>",
    )
    argutils.add_commit_args(parser, default=False)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf_interactive(args)
    # or e.g. Cerebrum.logutils.autoconf("cronjob", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    changes = update_expire_dates(db)
    write_report(args.fname, changes)

    if args.commit:
        logger.info("Commiting changes")
        db.commit()
    else:
        logger.info("Rolled back changes")
        db.rollback()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
