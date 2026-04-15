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
This is a script for changing the state of guest users.

Guest users that have been allocated and have passed the requested
period when this script runs will be in release_quarantine. That means
that every step that needs to be done to make the guest user ready for
new requests is done, except removing the quarantine.

Guest users that have been in quarantine and have passed the
quarantine period when this script runs will be made available for new
requests.

The script should preferably run once a day.
"""

from __future__ import print_function
import getopt
import sys
import mx

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.modules.PosixUser import PosixUser
from Cerebrum.modules.bofhd_requests.request import BofhdRequests

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
grp = Factory.get('Group')(db)
logger = Factory.get_logger("cronjob")
today = mx.DateTime.today()

db.cl_init(change_program="release_guests")

# This function is taken from bofhd_guestaccount_utils.py


def update_group_memberships(account_id):
    """Make sure that the account is a member of exactly the
    groups specified in cereconf.GUESTS_DEFAULT_FILEGROUP and
    cereconf.GUESTS_MEMBER_GROUPS.

    """
    user = PosixUser(db)
    user.find(account_id)
    gr = Factory.get("Group")(db)
    gr.find_by_name(cereconf.GUESTS_DEFAULT_FILEGROUP)
    user.gid_id = gr.entity_id
    user.write_db()
    req_groups = [gr.entity_id]
    # Add guest to the required groups
    for gr_name in cereconf.GUESTS_MEMBER_GROUPS:
        gr.clear()
        gr.find_by_name(gr_name)
        req_groups.append(gr.entity_id)
        member = gr.has_member(account_id)
        if member:
            gr.remove_member(account_id)
            member = False
        if not member:
            gr.add_member(account_id)
    # Expel guest from any extra groups
    for row in gr.search(member_id=account_id):
        if row['group_id'] not in req_groups:
            gr.clear()
            gr.find(row['group_id'])
            gr.remove_member(account_id)


# This is a hack to get the operator_id needed for add_request
uname2entity_id = {}


def get_operator_id(uname):
    account = Factory.get('Account')(db)
    if uname not in uname2entity_id:
        account.find_by_name(uname)
        uname2entity_id[uname] = account.entity_id
    return uname2entity_id[uname]


def release(guest, owner, start_date, dryrun=False):
    "Make guest ready for release_quarantine"

    if dryrun:
        grp.clear()
        grp.find(owner)
        logger.debug("DRYRUN: %s, with owner %s should be released %s" % (
            guest, grp.group_name, start_date))
        return
    # Set owner to None
    ac.populate_trait(co.trait_uio_guest_owner, target_id=None)
    logger.debug("Removed owner_id in owner_trait for %s" % guest)
    # Set new password
    ac.set_password(ac.make_passwd(guest))
    ac.write_db()
    update_group_memberships(ac.entity_id)
    # Finally, register a request to archive the home directory.
    # A new directory will be created when archival has been done.
    br = BofhdRequests(db, co)
    br.add_request(get_operator_id('cerebrum'), br.now,
                   co.bofh_archive_user, ac.entity_id, None,
                   state_data=int(co.spread_uio_nis_user))
    logger.debug("Added archive_user request for %s" % guest)


def make_guest_available(guest, dryrun=False):
    """
    Check that guest is ready for new requests, and delete quarantine if so
    """

    # Check that home_status=on_disk. If not, the guest isn't available
    try:
        home_status = ac.get_home(spread=co.spread_uio_nis_user)
    except Errors.NotFoundError:
        logger.warning("Cannot get home for %s. Missing spread?" % guest)
        return

    if not home_status or home_status['status'] != co.home_status_on_disk:
        logger.warning("%s has home_status != on_disk. Cannot make available!",
                       guest)
        return
    # Check if there is a bofh_archive_user request for this user
    # If so, the user is not ready
    br = BofhdRequests(db, co)
    if br.get_requests(ac.entity_id, operation=co.bofh_archive_user):
        logger.debug("guest %s has a archive_user request. Not available!")
        return
    # Make guest available by removing quarantine. Everything else is ready
    if not dryrun:
        ac.delete_entity_quarantine(co.quarantine_guest_release)
        logger.debug("removing quarantine for %s" % guest)
    else:
        logger.debug("DRYRUN: should have removed quarantine for %s" % guest)


def release_guests(guests=[], dryrun=False):
    """
    1. Find allocated guest accounts that are out of date. Ready these
       accounts for release quarantine.

    2. Find release_quarantined guest accounts that are out of date
       and make them available for new requests.
    """
    if not guests:
        # Find all guest accounts
        for row in ac.list_traits(co.trait_uio_guest_owner, target_id=NotSet):
            e_id = row['entity_id']
            try:
                ac.clear()
                ac.find(e_id)
                uname = ac.account_name
            except Errors.NotFoundError:
                logger.error("No account with entity_id=%r", e_id)
                continue
            guests.append(uname)

    for guest in guests:
        ac.clear()
        ac.find_by_name(guest)
        trait = ac.get_trait(co.trait_uio_guest_owner)
        if trait is None:
            logger.error("%s is not a guest" % guest)
            continue

        # Only check accounts with active quarantine, that is guests
        # that are out of date
        for q in ac.get_entity_quarantine(co.quarantine_guest_release,
                                          only_active=True):
            # Check if guest has a temporary owner
            if trait['target_id'] is None:
                # No owner. Check if end of quarantine_period is reached
                if q['start_date'] + cereconf.GUESTS_QUARANTINE_PERIOD < today:
                    make_guest_available(guest, dryrun=dryrun)
            else:
                if q['start_date'] < today:
                    release(guest, trait['target_id'], q['start_date'].date,
                            dryrun=dryrun)
    if not dryrun:
        db.commit()


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
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hdg:', [
            'help', 'dryrun', 'guest'])
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

    release_guests(guests, dryrun=dryrun)


if __name__ == '__main__':
    main()
