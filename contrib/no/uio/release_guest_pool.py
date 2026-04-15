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
The typical guest account cleanup goes as follows:

1. Guest account is quarantined (from the initial guest allocation)
2. When the quarantine starts, this script will initialize release
3. process_bofhd_requests.py will archive the homedir
4. process_changes.py will create a new, empty homedir
5. This script will release the account back into the pool of available guest
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
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import getopt
import logging
import sys

import cereconf
import Cerebrum.logutils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.no.uio.bofhd_guestaccounts_utils import GuestUtils
from Cerebrum.modules.trait import trait_db
from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def get_account_by_name(db, account_name):
    ac = Factory.get("Account")(db)
    ac.find_by_name(account_name)
    return ac


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
    account_repr = "%s (%d)" % (account.account_name, account.entity_id)

    # Set owner-trait to None
    account.populate_trait(const.trait_uio_guest_owner, target_id=None)
    logger.debug("Cleared owner-trait for account %s", account_repr)

    # Set new password
    account.set_password(account.make_passwd(account.account_name))
    account.write_db()
    logger.debug("Reset password for account %s", account_repr)

    update_group_memberships(account)
    logger.debug("Reset group memberships for account %s", account_repr)

    # Finally, register a request to archive the home directory.
    # A new directory will be created when archival has been done.
    br = BofhdRequests(db, const)
    br.add_request(operator.entity_id, br.now,
                   const.bofh_archive_user, account.entity_id, None,
                   state_data=int(const.spread_uio_nis_user))
    logger.debug("Added homedir archive request for account %s", account_repr)


def finalize_release(account):
    """
    Add guest back into the available guest account pool.

    This finalizes the guest cleanup, after the old homedir has been archived,
    and a new homedir has been created.

    :param account: the guest account
    """
    db = account._db
    const = account.const
    account_repr = "%s (%d)" % (account.account_name, account.entity_id)

    # Check if account has a new homeidr (home_status=on_disk). If not, the
    # guest isn't available.
    try:
        home_status = account.get_home(spread=const.spread_uio_nis_user)
    except Errors.NotFoundError:
        logger.warning("No homedir for account %s - missing spread?",
                       account_repr)
        return False

    if not home_status or home_status['status'] != const.home_status_on_disk:
        logger.warning("Invalid homedir for %s - not on disk", account_repr)
        return False
    # Check if there is a bofh_archive_user request for this user
    # If so, the user is not ready
    br = BofhdRequests(db, const)
    if br.get_requests(account.entity_id, operation=const.bofh_archive_user):
        logger.debug("Pending archive request for account %s - must wait",
                     account_repr)
        return False
    # Make guest available by removing quarantine. Everything else is ready
    account.delete_entity_quarantine(const.quarantine_guest_release)
    logger.debug("Removed quarantine for account %s", account_repr)
    return True


def _iter_candicate_guests(db, guests=None):
    if guests:
        for username in guests:
            yield get_account_by_name(db, username)
        return

    # Find all guest accounts
    const = Factory.get("Constants")(db)
    for row in trait_db.search_traits(db,
                                      code=int(const.trait_uio_guest_owner)):
        yield get_account_by_id(db, int(row['entity_id']))


def release_guests(db, guests=None):
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

    for account in _iter_candicate_guests(db, guests):
        account_repr = "%s (%d)" % (account.account_name, account.entity_id)

        trait = account.get_trait(guest_owner_trait)
        if trait is None:
            logger.error("Account %s is not a guest", account_repr)
            continue
        owner_id = trait['target_id']

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


def usage(exitcode=0):
    print("""Usage: release_guests.py [options]
    -d || --dryrun
    -g || --guest

    The script checks specified guest(s) or all guest users.

    If a guest account is allocated and the end date for that
    allocation is reached, the guest account shall be put in
    release_quarantine.

    If a guest in release_quarantine has reached the end of the
    quarantine_period, make it available for new requests again.

    if --dryrun option is specified only reporting is done.
    """)
    sys.exit(exitcode)


def main():
    Cerebrum.logutils.autoconf("cronjob", None)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hdg:', [
            'help', 'dryrun', 'guest='])
    except getopt.GetoptError:
        usage(1)

    guests = []
    dryrun = False
    for opt, val in opts:
        if opt in ('--help', '-h'):
            usage()
        elif opt in ('--dryrun', '-d'):
            dryrun = True
        elif opt in ('--guest', '-g'):
            if '-' in val:
                first, last = val.split('-')
                prefix = first.rstrip('0123456789')
                first = int(first[len(prefix):])
                last = int(last)
                for i in range(first, last+1):
                    guests.append('%s%03d' % (prefix, i))
            else:
                guests.append(val)

    prog = "release_guests"
    commit = not dryrun

    db = Factory.get('Database')()
    db.cl_init(change_program=prog)

    logger.info("Start %s", prog)

    release_guests(db, guests)

    if commit:
        logger.info("commiting changes")
        db.commit()
    else:
        logger.info("rolling back changes (dryrun)")
        db.rollback()
    logger.info("Done %s", prog)


if __name__ == '__main__':
    main()
