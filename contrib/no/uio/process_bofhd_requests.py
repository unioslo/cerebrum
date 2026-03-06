#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2026 University of Oslo, Norway
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
Process bofhd requests for UiO.

This script processes selected request types from the
:mod:`Cerebrum.modules.bofhd_requests` module.

These requests are typically changes that:

1. Are costly, and should not delay the script/process that caused them
2. Should be delayed until a specific point in time
3. Adds complexity to an otherwise simple function

More specifically, these changes mosly involves moving or archiving user home
directories.

There are other scripts with similar or related behaviour:

- ``process_changes.py`` deals with *creating* home directories.  This
  operation is typically triggered by the *change log*, rather than being bofhd
  requests.

- ``process_sympa_request.py`` creates and removes email lists from bofhd
  requests.

- ``preprocess-move-students.py`` creates *move* requests for this script.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import contextlib
import datetime
import logging
import os

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.modules.bofhd_requests import process_requests
from Cerebrum.modules.no.uio import reguser
from Cerebrum.utils import date as date_utils

logger = logging.getLogger(__name__)

RequestProcessor = process_requests.SimpleRequestProcessor

# Default homedir spread (for user delete/archive).  We cant't really support
# archiving other homedirs, as we only have one "generation" counter.
constants_cls = Factory.get('Constants')
default_spread = six.text_type(constants_cls.spread_uio_nis_user)


def _get_entity_by_id(db, factory_name, entity_id):
    obj = Factory.get(factory_name)(db)
    obj.find(int(entity_id))
    return obj


def _get_account_by_id(db, entity_id, posix=False):
    return _get_entity_by_id(
        db, "PosixUser" if posix else "Account", entity_id)


def _get_disk_by_id(db, entity_id):
    return _get_entity_by_id(db, "Disk", entity_id)


def _get_group_by_id(db, entity_id, posix=False):
    return _get_entity_by_id(db, "PosixGroup" if posix else "Group", entity_id)


def _get_host_by_id(db, entity_id):
    return _get_entity_by_id(db, "Host", entity_id)


def _get_initial_account(db):
    obj = Factory.get("Account")(db)
    obj.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return obj


@contextlib.contextmanager
def operator_context(db, requestee_id):
    """
    Set temporary operator context from request.

    Sets changelog operator from *requestee_id*, with fallback to a default if
    the id no longer exists.  Yields an operator name for use in reguser
    commands.
    """
    # Get operator id (changelog) and name (reguser script)
    try:
        _operator = _get_account_by_id(db, requestee_id)
        operator_id = _operator.entity_id
        operator_name = _operator.account_name
    except Errors.NotFoundError:
        _operator = _get_initial_account(db)
        operator_id = _operator.entity_id
        # TODO: Why is this hard-coded to "cerebrum"?
        operator_name = "cerebrum"

    old_prog, old_id = db.change_program, db.change_by
    db.cl_init(change_program=old_prog, change_by=operator_id)
    try:
        yield operator_name
    finally:
        db.cl_init(change_program=old_prog, change_by=old_id)


def get_home_disk(account, spread=None):
    """ Get homedir id and disk-id for a given account. """
    if spread is None:
        spread = account.const.get_constant(account.const.Spread,
                                            default_spread)
    home = account.get_home(spread)
    if home['home'] is None and home['disk_id']:
        return (int(home['homedir_id']), int(home['disk_id']))
    raise Errors.NotFoundError("no home disk")


def proc_move_user(db, r, dryrun=True, **kwargs):
    """
    Move user homedir from request.

    This operation is intended to process br_move_user and br_move_user_now
    requests.  It requires:

      - request_id
      - requestee_id (operator that requested the change)
      - entity_id (of the account to move)
      - desitination_id (entity id of the target disk)
      - state_date (a spread identifying the homedir to move)
    """
    #
    # setup - find and check: account, old home, new home
    #
    try:
        # must be a PosixAccount - as we need uid and gid for mvuser
        account = _get_account_by_id(db, r['entity_id'], posix=True)
    except Errors.NotFoundError:
        logger.error("proc_move_user: posix account id=%d not found",
                     r['entity_id'])
        # TODO: False? This request will probably never succeed...
        return False

    account_repr = "%s (%d)" % (account.account_name, account.entity_id)
    if account.is_expired():
        logger.warning("proc_move_user: account %s is expired", account_repr)
        # TODO: False? This request will probably never succeed...
        return False

    const = account.const
    spread = const.get_constant(const.Spread, r['state_data'])
    try:
        # TODO: should we not check the current status?
        homedir_id, disk_id = get_home_disk(account, spread)
        old_disk = _get_disk_by_id(db, disk_id).path
    except Errors.NotFoundError:
        logger.error("proc_move_user: no homedir disk for %s", account_repr)
        # TODO: False? This request will probably never succeed...
        return False

    try:
        new_disk = _get_disk_by_id(db, r['destination_id']).path
    except Errors.NotFoundError:
        logger.error("proc_move_user: invalid homedir disk (%r) for %s",
                     r['destination_id'], account_repr)
        # TODO: False? This request will probably never succeed...
        return False

    if new_disk == old_disk:
        logger.warning("proc_move_user: Account %s is already on target disk",
                       account_repr)
        return True

    #
    # move account from old host/disk to new host/disk
    #
    runner = reguser.ReguserCommands(dryrun=dryrun, remote_dryrun=False,
                                     remote_debug=False)
    with operator_context(db, r['requestee_id']) as operator_name:
        group = _get_group_by_id(db, account.gid_id, posix=True)

        if runner.move_user(user=account.account_name,
                            uid=int(account.posix_uid),
                            gid=int(group.posix_gid),
                            old_disk=old_disk,
                            new_disk=new_disk,
                            operator=operator_name):
            logger.info("proc_move_user: Moved account %s from %s to %s",
                        account_repr, old_disk, new_disk)
            account.set_homedir(current_id=homedir_id,
                                disk_id=r['destination_id'])
            account.write_db()
            return True
        else:
            logger.error(
                "proc_move_user: Failed to move account %s from %s to %s",
                account_repr, old_disk, new_disk)
            return False


#
# Archive user and archive helpers
#


def archive_user(account, spread, operator_name, dryrun=True):
    """ Archive a user account homedir """
    db = account._db
    const = account.const
    account_repr = "%s (%d)" % (account.account_name, account.entity_id)
    try:
        homedir_id, disk_id = get_home_disk(account, spread)
        old_disk = _get_disk_by_id(db, disk_id).path
    except Errors.NotFoundError:
        logger.error("archive_user: unable to archive - no homedir for %s",
                     account_repr)
        return False

    # Archive homedir
    generation_trait = account.get_trait(const.trait_account_generation) or {}
    generation = (generation_trait.get('numval') or 0) + 1
    homedir = os.path.join(old_disk, account.account_name)
    runner = reguser.ReguserCommands(dryrun=dryrun, remote_dryrun=False,
                                     remote_debug=False)

    if runner.delete_user(username=account.account_name, homedir=homedir,
                          deleted_by=operator_name, generation=generation):
        account.set_homedir(current_id=homedir_id,
                            status=const.home_status_archived)
        account.populate_trait(const.trait_account_generation,
                               numval=generation)
        account.write_db()
        logger.info("archive_user: archived homedir %s for account %s",
                    homedir, account_repr)
        return True
    else:
        logger.error("archive_user: archive homedir %s failed for account %s",
                     homedir, account_repr)
        return False


def proc_archive_user(db, r, dryrun=True, **kwargs):
    """
    Archive a user homedir on request.

    This action *can* archive any user homedir, but really only runs on
    *release_guest*, which starts the process of resetting an active guest
    account (guestNNN/gjestNNN).

    The archive operation causes a homedir:modify.  This change is processed by
    ``process_changes.py``, which creates a new homedir and puts the guest back
    into the uio guest account pool.
    """
    try:
        account = _get_account_by_id(db, r['entity_id'])
    except Errors.NotFoundError:
        logger.error("proc_archive_user: account id=%d not found",
                     r['entity_id'])
        return False
    const = account.const
    spread = const.get_constant(const.Spread, default_spread)
    with operator_context(db, r['requestee_id']) as operator_name:
        return archive_user(account, spread, operator_name, dryrun=dryrun)


#
# Delete user and delete helpers
#


def _needs_archiving(account, spread):
    """ Check if an account homedir needs archiving. """
    const = account.const
    try:
        home = account.get_home(spread)
        status = const.AccountHomeStatus(home['status'])
    except Errors.NotFoundError:
        status = None

    if status == const.home_status_on_disk:
        logger.debug("account id=%d homedir on disk", account.entity_id)
        return True

    if status is None:
        logger.debug("account id=%d has no homedir", account.entity_id)
        return False

    logger.debug("account id=%d homedir not on disk (%s)",
                 account.entity_id, six.text_type(status))
    return False


def assert_dfg(account):
    """
    Ensure that a posix user dfg is its personal file group.

    This must be done when deleting a posix user, to ensure that it is restored
    correctly if and when that happens.
    """
    account_repr = "%s (%d)" % (account.account_name, account.entity_id)
    db = account._db
    try:
        pu = _get_account_by_id(db, account.entity_id, posix=True)
    except Errors.NotFoundError:
        logger.debug("assert_dfg: account %s is not a posix account",
                     account_repr)
        return

    logger.debug("assert_dfg: checking posix account %s", account_repr)
    default_group = pu.gid_id

    # The account is a PosixUser, special care needs to be taken with
    # regards to its default file group (dfg)
    personal_fg = pu.find_personal_group()
    if personal_fg is None:
        # Create a new personal file group
        op = _get_initial_account(db)
        with pu._new_personal_group(op.entity_id) as new_group:
            personal_fg = new_group
            roles = GroupRoles(db)
            roles.add_admin_to_group(pu.entity_id, personal_fg.entity_id)
            pu.map_user_spreads_to_pg()
        logger.info("assert_dfg: created personal fg for %s - %s (%d)",
                    account_repr, personal_fg.group_name,
                    personal_fg.entity_id)

    # If user has a personal group, but it currently isn't a posix group.
    # This scenario should never really occur, but hey, this is Cerebrum.
    if not personal_fg.has_extension('PosixGroup'):
        pg = Factory.get('PosixUser')(db)
        pg.populate(parent=personal_fg)
        pg.write_db()
        personal_fg = pg
        logger.info("assert_dfg: posix promoted %s (%d)",
                    account_repr, personal_fg.group_name,
                    personal_fg.entity_id)

    # Set personal_fg to be dfg for the user.
    if personal_fg.entity_id != default_group:
        pu.gid_id = personal_fg.entity_id
        pu.write_db()
        default_group = personal_fg.entity_id
        logger.info("assert_dfg: updated dfg for %s to %s (%d)",
                    account_repr, personal_fg.group_name,
                    personal_fg.entity_id)

    return default_group


def proc_delete_user(db, r, dryrun=True, **kwargs):
    """
    Delete user and archive homedir from request.

    This operation is intended to process br_delete_user requests, and
    requires:

      - request_id
      - requestee_id (operator that requested the change)
      - entity_id (of the account to delete)
    """
    try:
        account = _get_account_by_id(db, r['entity_id'])
    except Errors.NotFoundError:
        logger.error("proc_delete_user: account id=%d not found",
                     r['entity_id'])
        return False
    account_repr = "%s (%d)" % (account.account_name, account.entity_id)
    if account.is_deleted():
        logger.warning("proc_delete_user: Account %s is deleted", account_repr)
        return True

    # TODO: Should we not archive *all* networked homedirs?
    const = account.const
    spread = const.get_constant(const.Spread, default_spread)

    with operator_context(db, r['requestee_id']) as operator_name:
        if _needs_archiving(account, spread):
            if not archive_user(account, spread, operator_name,
                                dryrun=dryrun):
                return False

        # set expire date
        account.expire_date = datetime.date.today()
        account.write_db()
        logger.info("proc_delete_user: set expire date for %s to %s",
                    account_repr, account.expire_date)

        # remove spreads
        for s in account.get_spread():
            account.delete_spread(s['spread'])
            logger.info("proc_delete_user: removed %s spread code=%d",
                        account_repr, s['spread'])

        # ensure correct dfg if posix user
        dfg_id = assert_dfg(account)

        # remove user from all groups except dfg
        group = Factory.get('Group')(account._db)
        for g in group.search(member_id=account.entity_id,
                              indirect_members=False,
                              filter_expired=False):
            if g['group_id'] == dfg_id:
                # all posixuser-objects have to keep their membership
                # in their default group due to a FK-constraint from
                # posix_user to group_member
                continue
            group.clear()
            group.find(g['group_id'])
            group.remove_member(account.entity_id)
            logger.info("proc_delete_user: removed %s from group %s (%d)",
                        account_repr, group.group_name, group.entity_id)

        # clear password
        account.delete_password()
        logger.info("proc_delete_user: cleared password for %s", account_repr)
        return True


#
# Quarantine refresh
#


def proc_quarantine_refresh(db, r, dryrun=True, **kwargs):
    """
    Add a quarantine refresh event from request.

    This is a special change that simply adds a changelog-event for
    quarantines.  The request is issued by `process_changes.py` -- see this
    script for details.
    """
    cl_const = Factory.get('CLConstants')(db)
    with operator_context(db, r['requestee_id']):
        db.log_change(r['entity_id'], cl_const.quarantine_refresh, None)
        return True


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Process homedir management and other delayed bofhd request tasks"
        ),
    )
    # TODO: For proper debugging and testing, We may want separate --dryrun
    # override flags for the clhandler and the sympa commands
    commit_mutex = parser.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help="Run remote scripts and commit changes",
    )
    commit_mutex.add_argument(
        "--dryrun",
        action="store_false",
        dest="commit",
        help="Don't run scripts or commit changes (default)",
    )
    commit_mutex.set_defaults(commit=False)

    parser.add_argument(
        "-t", "--type",
        dest="category",
        action="append",
        choices=("move", "delete", "quarantine"),
        required=True,
        help="Process request category %(metavar)s",
        metavar="TYPE",
    )

    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args()
    Cerebrum.logutils.autoconf("daily", args)
    dryrun = not args.commit

    logger.info('start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    const = Factory.get('Constants')(db)
    process_operation = RequestProcessor(db, dryrun=dryrun)

    operations = []

    if "quarantine" in args.category:
        operations.append({
            'op_type': const.bofh_quarantine_refresh,
            'callback': proc_quarantine_refresh,
        })

    if "delete" in args.category:
        operations.append({
            'op_type': const.bofh_archive_user,
            'callback': proc_archive_user,
            'delay': date_utils.to_seconds(hours=2),
        })
        operations.append({
            'op_type': const.bofh_delete_user,
            'callback': proc_delete_user,
            'delay': date_utils.to_seconds(hours=2),
        })

    if "move" in args.category:
        operations.append({
            'op_type': const.bofh_move_user_now,
            'callback': proc_move_user,
            'delay': date_utils.to_seconds(days=1),
        })

    if "move" in args.category and process_requests.is_ok_batch_time():
        operations.append({
            'op_type': const.bofh_move_user,
            'callback': proc_move_user,
            'delay': date_utils.to_seconds(days=1),
        })

    logger.debug("processing requests...")
    for kwargs in operations:
        process_operation(**kwargs)

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
