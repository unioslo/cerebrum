#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
Deactivate quarantined email accounts.

This is a companion script for ``contrib/quarantine_accouns.py`` and
``contrib/no/deactivate_quarantined_accounts.py``.

At UiO we want to remove the email spread for accounts that about to be
disabled.  This is to ensure that accounts are disabled in our e-mail system at
an appropriate time, which is typically at the same time as the disable-account
quarantine takes effect.

All of this would normally be handled by `Account.deactivate()`, but we want to
run this particular `deactivate()` operation before all the other:

1. Account owner is no longer affiliated
2. After 3 days, accounts are quarantined with a future start date
   (quarantine_accounts.py)
3. After a total of 29 days, quarantine takes effect
4. As the quarantine takes effect, the email spread (and email target) is
   removed (this script)
5. After a total of 60 days, account is disabled (i.e. homedir, spreads, etc is
   removed by deactivate_quarantined_accounts.py)
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
import Cerebrum.Errors
from Cerebrum.database.ctx import db_context
from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailTarget
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def get_quarantined_accounts(db, quarantines):
    """
    Get all accounts that has been recently quarantined.

    :param quarantines:
        Only consider the given quarantines.

        If ``None`` - consider all quarantines.  Otherwise this must be a
        single quarantine type, or a collection of quarantine types.
    """
    ac = Factory.get("Account")(db)
    today = datetime.date.today()
    for row in ac.list_entity_quarantines(
            entity_types=(ac.const.entity_account,),
            quarantine_types=quarantines,
            only_active=False,
            ):
        start_date = date_compat.get_date(row['start_date'])
        end_date = date_compat.get_date(row['end_date'])
        disable_until = date_compat.get_date(row['disable_until'])
        if start_date and start_date > today:
            # Quarantine must have taken effect *before* today.
            continue
        if end_date and end_date <= today:
            # Quarantine has already *ended* - this shouldn't really happen,
            # but as long as an end-date can exist we should consider it.
            continue
        if disable_until and disable_until >= today:
            # This quarantine is currently disabled, and should be ignored.
            # We may consider ignoring the quarantine disable mechanic here,
            # not sure if it makes sense for the email spread/account...
            continue
        yield row['entity_id']


def get_accounts_with_spread(db, spread):
    """ Get all accounts with a given spread. """
    ac = Factory.get("Account")(db)
    for row in ac.list_entity_quarantines(
            entity_types=(ac.const.entity_account,),
            spreads=(spread,)):
        yield row['entity_id']


def get_accounts_with_targets(db):
    """ Get all accounts with an active email target. """
    et = EmailTarget(db)
    for row in et.list_email_targets_ext(
            target_type=et.const.email_target_account):
        yield row['target_id'], row['target_entity_id']


class EmailAccountManager(object):
    """ Disable quarantined email accounts with a given spread. """

    def __init__(self, db, email_spread, disable_quarantines):
        """
        :param email_spread:
            The email spread to manage/remove

        :param disable_quarantines:
            One or more quarantines that should deactivate the email account.

            If ``None``, all quarantines will trigger an email account removal.
        """
        self.db = db
        self.spread = email_spread
        self.quarantines = disable_quarantines

    def _list_candidates(self):
        logger.debug("finding candidates...")
        targets = dict(get_accounts_with_targets(self.db))
        candidates = set(targets.values())
        logger.debug("found %d accounts with email target",
                     len(candidates))

        with_spread = set(get_accounts_with_spread(self.db, self.spread))
        logger.debug("found %d accounts with spread %s",
                     len(with_spread), self.spread)

        logger.debug("mismatch (target - spread): %d",
                     len(candidates - with_spread))
        logger.debug("mismatch (spread - target): %d",
                     len(with_spread - candidates))

        candidates = candidates & with_spread

        quarantined = set(get_quarantined_accounts(self.db, self.quarantines))
        logger.debug("found %d accounts with quarantines %s",
                     len(quarantined), self.quarantines)
        candidates = candidates & quarantined

        logger.info("found %d candidates", len(candidates))
        return sorted(candidates)

    def _disable_account(self, account):
        account.delete_spread(self.spread)
        logger.info("removed spread %s from account %s (%d)",
                    self.spread, account.account_name, account.entity_id)

    def __call__(self, limit=0):
        deactivated = 0
        for account_id in self._list_candidates():
            account = get_account_by_id(self.db, account_id)
            self._disable_account(account)
            deactivated += 1
            if limit and deactivated >= limit:
                logger.info("reached limit (%d), stopping", limit)
                break

        logger.info("deactivated %d email accounts", deactivated)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Deactivate disabled email accounts",

    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after deactivating %(metavar)s accounts",
        metavar="N",
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)

    Cerebrum.logutils.autoconf("cronjob", args)
    logger.info("start %s", parser.prog)
    logger.info("args: %s", repr(args))

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    deactivate_email_accounts = EmailAccountManager(
        db,
        email_spread=const.spread_exchange_account,
        disable_quarantines=(const.quarantine_auto_no_aff,),
    )

    with db_context(db, dryrun=(not args.commit)):
        db.cl_init(change_program=parser.prog)
        deactivate_email_accounts(args.limit)

    logger.info("done %s", parser.prog)


if __name__ == "__main__":
    main()
