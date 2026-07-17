#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2026 University of Oslo, Norway
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
This script returns guest accounts back into the guest account pool.

Release process
----------------
The typical guest account cleanup goes through the following steps:

1. Guest account is quarantined (from the initial guest allocation)
2. This script starts the release process when the quarantine takes effect.
3. `process_bofhd_requests.py` will then archive the homedir
4. `process_changes.py` will create a new, empty homedir
5. After `cereconf.GUESTS_QUARANTINE_PERIOD` days, this script will finalize
   the release, and move the account back into the pool of available guest
   accounts.

Glossary
--------
Guest account pool
    A set of guest accounts that are ready to be reserved for use.

Reserved guest account
    A guest account that has been taken out of the guest account pool and is
    allocated to an owner group.  This account is either reserved for use,
    or in active use.

Released guest account
    A guest account that is in the guest account pool, ready to be reserved.

    Releasing a guest is a multi-step process to move a guest account back into
    the guest account pool.

Owner trait
    Guest accounts that belong to the guest account pool are identified with
    the ``trait_uio_guest_owner`` trait.

    The 'target_id' indicates if the guest account is allocated to a given
    owner group.  This value is set whenever the account has been reserved for
    use, and unset when the account is released.

Guest quarantine
    All reserved guests will have the `quarantine_guest_release` quarantine.

    When the account is allocated to an owner, the quarantine will be set to a
    future date.  When the quarantine takes effect, the guest is ready to be
    released back into the guest account pool.


TODO
----
We may want to move the homedir archive and re-create here, rather than relying
on other scripts to run for this process.  It would make everything a bit
easier to follow.

All functionality related to the guest account pool should probably be moved
into its own module.  A lot code related to the guest account processes is
duplicated, and spread across multiple modules.
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
import textwrap

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.database.ctx import db_context
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.no.uio.bofhd_guestaccounts_utils import GuestUtils
from Cerebrum.modules.trait import trait_db
from Cerebrum.utils import date_compat
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def get_account_by_name(db, account_name):
    ac = Factory.get("Account")(db)
    ac.find_by_name(account_name)
    return ac


def get_account_repr(account):
    return "%s (%d)" % (account.account_name, account.entity_id)


def update_group_memberships(account):
    """ Reset guest account group memberships. """
    db = account._db
    utils = GuestUtils(db, logger.getChild("guest_utils"))
    utils.update_group_memberships(int(account.entity_id))


def prepare_release(account, operator):
    """
    Initialize guest account release.

    This does the initial guest cleanup, and requests archiving of the guest
    homedir.

    :param account: the guest account
    """
    db = account._db
    const = account.const
    account_repr = get_account_repr(account)

    # Reset owner trait (unset all values)
    trait_db.set_trait(db, int(account.entity_id), int(account.entity_type),
                       int(const.trait_uio_guest_owner))

    # Set new password
    account.set_password(account.make_passwd(account.account_name))
    account.write_db()

    update_group_memberships(account)
    logger.info("Reset group memberships for account %s", account_repr)

    # Finally, register a request to archive the home directory.
    # A new directory will be created when archival has been done.
    br = BofhdRequests(db, const)
    br.add_request(operator.entity_id, br.now,
                   const.bofh_archive_user, account.entity_id, None,
                   state_data=int(const.spread_uio_nis_user))
    logger.info("Added homedir archive request for account %s", account_repr)


def finalize_release(account):
    """
    Add guest back into the available guest account pool.

    This finalizes the guest cleanup, after the old homedir has been archived,
    and a new homedir has been created.

    :param account: the guest account
    """
    db = account._db
    const = account.const
    account_repr = get_account_repr(account)

    # Check if there is an archive request in queue for this user.  If so, the
    # user is not ready to be released.
    br = BofhdRequests(db, const)
    if br.get_requests(account.entity_id, operation=const.bofh_archive_user):
        logger.warning("Pending archive request for account %s - must wait",
                       account_repr)
        return False

    # Check if account has a new homedir on disk.  If not, the user is not
    # ready to be released.
    try:
        home_status = account.get_home(spread=const.spread_uio_nis_user)
    except Errors.NotFoundError:
        logger.error("No homedir for account %s - missing spread?",
                     account_repr)
        return False
    if home_status['status'] != const.home_status_on_disk:
        logger.warning("Invalid homedir for %s - not on disk", account_repr)
        return False
    # Make guest available by removing quarantine. Everything else is ready
    account.delete_entity_quarantine(const.quarantine_guest_release)
    logger.info("Removed quarantine for account %s", account_repr)
    return True


def select_guests(db, usernames):
    """ Get guest accounts from a list of usernames. """
    owner_trait = Factory.get("Constants")(db).trait_uio_guest_owner
    for username in usernames:
        account = get_account_by_name(db, username)
        trait = account.get_trait(owner_trait)
        if not trait:
            logger.warning("Ignoring %s (%d) - not a guest account",
                           account.account_name, account.entity_id)
            continue
        yield account


def list_guests(db):
    """ Get all guest accounts. """
    owner_trait = Factory.get("Constants")(db).trait_uio_guest_owner
    for row in trait_db.search_traits(db, code=int(owner_trait)):
        yield get_account_by_id(db, int(row['entity_id']))


def release_guests(db, guest_accounts):
    """
    Process guests that are ready for release back into the guest account pool.
    """
    today = datetime.date.today()
    quarantine_offset = datetime.timedelta(
        days=int(cereconf.GUESTS_QUARANTINE_PERIOD),
    )
    const = Factory.get("Constants")(db)
    guest_owner_trait = const.trait_uio_guest_owner
    guest_quarantine = const.quarantine_guest_release
    operator = get_account_by_name(db, "cerebrum")

    for account in guest_accounts:
        account_repr = get_account_repr(account)
        owner_id = account.get_trait(guest_owner_trait)['target_id']

        for row in account.get_entity_quarantine(guest_quarantine,
                                                 only_active=True):
            start_date = date_compat.get_date(row['start_date'],
                                              allow_none=False)
            if owner_id is not None and start_date < today:
                # Guest account has an owner and is quarantined.
                # It should be reset and added back into the pool, so let's
                # initiate that process.
                prepare_release(account, operator)
                logger.info("Initiated guest release for %s", account_repr)

            elif owner_id is None and start_date + quarantine_offset < today:
                # No owner, but quarantined - and quarantine is old enough
                # that the homedir should have been archived.
                # This guest account is probably ready for release, so let's
                # check and try to release.
                if finalize_release(account):
                    logger.info("Released guest %s", account_repr)


def guest_range(value):
    """
    Convert a guest range into individual usernames.

    :param str value:
        A value on format <prefix><start>-<end>, e.g. guest150-159

    :returns:
        Returns an iterable of usernames.
    """
    try:
        prefix_start, end_raw = value.split('-')
        prefix = prefix_start.rstrip('0123456789')
        start = int(prefix_start[len(prefix):])
        end = int(end_raw)
    except (TypeError, ValueError) as e:
        raise ValueError("Invalid range %s (%s)" % (repr(value), e))
    for i in range(start, end + 1):
        yield "{}{:03d}".format(prefix, i)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Release guests back into the guest account pool",
        epilog=textwrap.dedent(
            """
            This script prepares and finalizes guest accounts for release back
            into pool of available guest accounts.

            Processing can be restricted to a selection of guest accounts with
            the --guest or --range options, e.g.:

                %(prog)s --guest guest132 --range guest150-159

            If no accounts are selected, the script will process all guest
            accounts that are ready for release.
            """
        ).lstrip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-g", "--guest",
        dest="guests",
        action="append",
        help="Process guest account %(metavar)s (repeatable)",
        metavar="USERNAME",
    )
    parser.add_argument(
        "-r", "--range",
        dest="guests",
        action=argutils.ExtendAction,
        type=guest_range,
        help="Process a range of guest accounts",
        metavar="RANGE",
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    with db_context(Factory.get('Database')(), dryrun=not args.commit) as db:
        db.cl_init(change_program=parser.prog)

        if args.guests:
            guests = select_guests(db, args.guests)
        else:
            guests = list_guests(db)

        release_guests(db, sorted(guests, key=lambda ac: ac.account_name))

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
