#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2023 University of Oslo, Norway
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

This script reads from the bofhd_request table in the database and picks the
requests of the given types for processing.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)

import argparse
import datetime
import logging
import pickle

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.modules import Email
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.bofhd_requests import process_requests
from Cerebrum.utils import json
from Cerebrum.utils.argutils import get_constant

logger = logging.getLogger(__name__)

SSH_CMD = "/usr/bin/ssh"
SUDO_CMD = "sudo"
SSH_CEREBELLUM = [SSH_CMD, cereconf.ARCHIVE_USER_SERVER]

DEBUG = False
EXIT_SUCCESS = 0

constants_cls = Utils.Factory.get('Constants')
operations_map = process_requests.OperationsMap()

# plaintext-constants
sympa_create_op = six.text_type(constants_cls.bofh_sympa_create)
sympa_remove_op = six.text_type(constants_cls.bofh_sympa_remove)
move_user_op = six.text_type(constants_cls.bofh_move_user)
move_user_now_op = six.text_type(constants_cls.bofh_move_user_now)
quarantine_refresh_op = six.text_type(constants_cls.bofh_quarantine_refresh)
archive_user_op = six.text_type(constants_cls.bofh_archive_user)
delete_user_op = six.text_type(constants_cls.bofh_delete_user)

# TODO: now that we support multiple homedirs, we need to which one an
# operation is valid for.  This information should be stored in
# state_data, but for e-mail commands this column is already used for
# something else.  The proper solution is to change the databasetable
# and/or letting state_data be pickled.
default_spread = six.text_type(constants_cls.spread_uio_nis_user)


@operations_map(sympa_create_op, delay=2*60)
def proc_sympa_create(db, request):
    """Execute the request for creating a sympa mailing list.

    :param request:
        a dict-like object describing the sympa list creation request
    """

    try:
        listname = get_address(db, request["entity_id"])
    except Errors.NotFoundError:
        logger.info("Sympa list address id:%s is deleted! No need to create",
                    request["entity_id"])
        return True

    try:
        state = json.loads(request["state_data"])
    except ValueError:
        state = None

    # Remove this when there's no chance of pickled data
    if state is None:
        try:
            state = pickle.loads(request["state_data"])
        except Exception:
            pass

    if state is None:
        logger.error("Cannot parse request state for sympa list=%s: %s",
                     listname, request["state_data"])
        return True

    try:
        host = state["runhost"]
        profile = state["profile"]
        description = state["description"]
        admins = state["admins"]
        admins = ",".join(admins)
    except KeyError:
        logger.error("No host/profile/description specified for sympa list %s",
                     listname)
        return True

    # 2008-08-01 IVR FIXME: Safe quote everything fished out from state.
    cmd = [cereconf.SYMPA_SCRIPT, host, 'newlist',
           listname, admins, profile, description]
    return Utils.spawn_and_log_output(cmd) == EXIT_SUCCESS


@operations_map(sympa_remove_op, delay=2*60)
def proc_sympa_remove(db, request):
    """Execute the request for removing a sympa mailing list.

    :param request:
        a dict-like object containing all the parameters for sympa list removal
    """

    try:
        state = json.loads(request["state_data"])
    except ValueError:
        state = None

    # Remove this when there's no chance of pickled data
    if state is None:
        try:
            state = pickle.loads(request["state_data"])
        except Exception:
            pass

    if state is None:
        logger.error("Cannot parse request state for sympa request %s: %s",
                     request["request_id"], request["state_data"])
        return True

    try:
        listname = state["listname"]
        host = state["run_host"]
    except KeyError:
        logger.error("No listname/runhost specified for request %s",
                     request["request_id"])
        return True

    cmd = [cereconf.SYMPA_SCRIPT, host, 'rmlist', listname]
    return Utils.spawn_and_log_output(cmd) == EXIT_SUCCESS


def get_address(db, address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))


@operations_map(move_user_op, move_user_now_op, delay=24*60)
def proc_move_user(db, r):
    try:
        account, uname, old_host, old_disk = get_account_and_home(
            db, r['entity_id'], type='PosixUser',
            spread=r['state_data'])
        new_host, new_disk = get_disk(db, r['destination_id'])
    except Errors.NotFoundError:
        logger.error("move_request: user %i not found", r['entity_id'])
        return False
    if account.is_expired():
        logger.warn("Account %s is expired, cancelling request",
                    account.account_name)
        return False
    process_requests.set_operator(db, r['requestee_id'])
    try:
        operator = get_account(db, r['requestee_id']).account_name
    except Errors.NotFoundError:
        # The mvuser script requires a valid address here.  We
        # may want to change this later.
        operator = "cerebrum"
    group = get_group(db, account.gid_id, grtype='PosixGroup')

    if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                 old_host, old_disk, new_host, new_disk, operator):
        logger.debug('user %s moved from %s to %s',
                     uname, old_disk, new_disk)
        spread = account.const.get_constant(account.const.Spread,
                                            default_spread)
        ah = account.get_home(spread)
        account.set_homedir(current_id=ah['homedir_id'],
                            disk_id=r['destination_id'])
        account.write_db()
        return True
    else:
        return new_disk == old_disk


@operations_map(quarantine_refresh_op, delay=0)
def proc_quarantine_refresh(db, r):
    """
    process_changes.py has added bofh_quarantine_refresh for the
    start/disable/end dates for the quarantines.  Register a
    quarantine_refresh change-log event so that changelog-based
    quicksync script can revalidate the quarantines.
    """
    cl_const = Utils.Factory.get('CLConstants')(db)
    process_requests.set_operator(db, r['requestee_id'])
    db.log_change(r['entity_id'], cl_const.quarantine_refresh, None)
    return True


@operations_map(archive_user_op, delay=2*60)
def proc_archive_user(db, r):
    const = constants_cls(db)
    spread = const.get_constant(const.Spread, default_spread)
    # TODO: check spread in r['state_data']
    account, uname, old_host, old_disk = get_account_and_home(
        db, r['entity_id'], spread=spread)
    operator = get_account(db, r['requestee_id']).account_name
    if delete_user(db, uname, old_host, '%s/%s' % (old_disk, uname),
                   operator, ''):
        try:
            home = account.get_home(spread)
        except Errors.NotFoundError:
            pass
        else:
            account.set_homedir(current_id=home['homedir_id'],
                                status=const.home_status_archived)
        return True
    else:
        return False


@operations_map(delete_user_op, delay=2*60)
def proc_delete_user(db, r):
    const = constants_cls(db)
    spread = const.get_constant(const.Spread, default_spread)
    # TODO: check spread in r['state_data']
    #
    # IVR 2007-01-25 We do not care if it's a posix user or not.
    # TVL 2013-12-09 Except that if it's a POSIX user, it should retain a
    #                personal file group.
    account, uname, old_host, old_disk = get_account_and_home(
        db, r['entity_id'], spread=spread)
    if account.is_deleted():
        logger.warn("%s is already deleted" % uname)
        return True
    process_requests.set_operator(db, r['requestee_id'])
    operator = get_account(db, r['requestee_id']).account_name
    et = Email.EmailTarget(db)
    try:
        et.find_by_target_entity(account.entity_id)
        es = Email.EmailServer(db)
        es.find(et.email_server_id)
        mail_server = es.name
    except Errors.NotFoundError:
        mail_server = ''

    if not delete_user(db, uname, old_host, '%s/%s' % (old_disk, uname),
                       operator, mail_server):
        return False

    account.expire_date = datetime.date.today()
    account.write_db()
    try:
        home = account.get_home(spread)
    except Errors.NotFoundError:
        pass
    else:
        account.set_homedir(current_id=home['homedir_id'],
                            status=const.home_status_archived)
    # Remove references in other tables
    # Note that we preserve the quarantines for deleted users
    # TBD: Should we have an API function for this?
    for s in account.get_spread():
        account.delete_spread(s['spread'])

    # Make sure the user's default file group is a personal group
    group = Utils.Factory.get('Group')(db)
    default_group = _get_default_group(db, account.entity_id)
    pu = Utils.Factory.get('PosixUser')(db)

    try:
        pu.find(account.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        # The account is a PosixUser, special care needs to be taken with
        # regards to its default file group (dfg)
        personal_fg = pu.find_personal_group()
        if personal_fg is None:
            # Create a new personal file group
            op = Utils.Factory.get('Account')(db)
            op.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            with pu._new_personal_group(op.entity_id) as new_group:
                personal_fg = new_group
                roles = GroupRoles(db)
                roles.add_admin_to_group(pu.entity_id, personal_fg.entity_id)
                pu.map_user_spreads_to_pg()
            logger.debug("Created group: '%s'. Group ID = %d",
                         personal_fg.group_name, personal_fg.entity_id)

        pg = Utils.Factory.get('PosixUser')(db)
        # If user has a personal group, but it currently isn't a posix group.
        # This scenario should never really occur, but hey, this is Cerebrum.
        if not personal_fg.has_extension('PosixGroup'):
            pg.populate(parent=personal_fg)
            pg.write_db()
            personal_fg = pg
        # Set group to be dfg for the user.
        if personal_fg.entity_id != default_group:
            pu.gid_id = personal_fg.entity_id
            pu.write_db()
            default_group = _get_default_group(db, account.entity_id)

    # Remove the user from groups
    group.clear()
    for g in group.search(member_id=account.entity_id,
                          indirect_members=False):
        group.clear()
        group.find(g['group_id'])
        #
        # all posixuser-objects have to keep their membership
        # in their default group due to a FK-constraint from
        # posix_user to group_member
        if g['group_id'] == default_group:
            logger.debug("Skipping default group %s for user %s",
                         group.group_name, account.account_name)
            continue
        group.remove_member(account.entity_id)

    # Remove password from user
    account.delete_password()

    return True


def _get_default_group(db, account_id):
    try:
        # only posix_user-objects have a default group
        account = Utils.Factory.get('PosixUser')(db)
        account.clear()
        account.find(account_id)
    except Errors.NotFoundError:
        return None
    return account.gid_id


def delete_user(db, uname, old_host, old_home, operator, mail_server):
    account = get_account(db, name=uname)
    const = account.const
    generation = account.get_trait(const.trait_account_generation)
    if generation:
        generation = generation['numval'] + 1
    else:
        generation = 1

    args = [
        SUDO_CMD, cereconf.RMUSER_SCRIPT,
        '--username', account.account_name,
        '--deleted-by', operator,
        '--homedir', old_home,
        '--generation', str(generation)
    ]
    if DEBUG:
        args.append('--debug')
    cmd = SSH_CEREBELLUM + [" ".join(args), ]

    if Utils.spawn_and_log_output(cmd, connect_to=[old_host]) == EXIT_SUCCESS:
        account.populate_trait(const.trait_account_generation,
                               numval=generation)
        account.write_db()
        return True
    return False


def move_user(uname, uid, gid, old_host, old_disk, new_host, new_disk,
              operator):
    args = [SUDO_CMD, cereconf.MVUSER_SCRIPT,
            '--user', uname,
            '--uid', str(uid),
            '--gid', str(gid),
            '--old-disk', old_disk,
            '--new-disk', new_disk,
            '--operator', operator]
    if DEBUG:
        args.append('--debug')
    cmd = SSH_CEREBELLUM + [" ".join(args), ]
    return (Utils.spawn_and_log_output(cmd, connect_to=[old_host, new_host]) ==
            EXIT_SUCCESS)


def get_disk(db, disk_id):
    disk = Utils.Factory.get('Disk')(db)
    disk.clear()
    disk.find(disk_id)
    host = Utils.Factory.get('Host')(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path


def get_account(db, account_id=None, name=None):
    assert account_id or name
    acc = Utils.Factory.get('Account')(db)
    if account_id:
        acc.find(account_id)
    elif name:
        acc.find_by_name(name)
    return acc


def get_account_and_home(db, account_id, type='Account', spread=None):
    if type == 'Account':
        account = Utils.Factory.get('Account')(db)
    elif type == 'PosixUser':
        account = Utils.Factory.get('PosixUser')(db)
    account.clear()
    account.find(account_id)
    if spread is None:
        spread = account.const.get_constant(account.const.Spread,
                                            default_spread)
    uname = account.account_name
    try:
        home = account.get_home(spread)
    except Errors.NotFoundError:
        return account, uname, None, None
    if home['home'] is None:
        if home['disk_id'] is None:
            return account, uname, None, None
        host, home = get_disk(db, home['disk_id'])
    else:
        host = None  # TODO:  How should we handle this?
        home = home['home']
    return account, uname, host, home


def get_group(db, group_id, grtype="Group"):
    if grtype == "Group":
        group = Utils.Factory.get('Group')(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(group_id)
    return group


def main():
    global DEBUG
    # TODO: DEBUG is the only global state left in this script.  We need to
    # figure out a better way to pass CLI-args into operations_map callbacks.

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--debug',
        dest='debug',
        action='store_true',
        help='Turn on debugging',
    )
    parser.add_argument(
        '-t', '--type',
        dest='types',
        action='append',
        choices=['email', 'sympa', 'move', 'quarantine', 'delete'],
        required=True,
    )
    parser.add_argument(
        '-m', '--max',
        dest='max_requests',
        default=999999,
        help='Perform up to this number of requests',
        type=int,
    )
    parser.add_argument(
        '-p', '--process',
        dest='process',
        action='store_true',
        help='Perform the queued operations',
    )
    args, _rest = parser.parse_known_args()

    has_move_arg = 'move' in args.types
    arg_group = parser.add_argument_group('Required for move_student requests')
    arg_group.add_argument(
        '--ou-perspective',
        dest='ou_perspective',
        default='perspective_fs',
    )
    arg_group.add_argument(
        '--emne-info-file',
        dest='emne_info_file',
        default=None,
        required=has_move_arg,
    )
    arg_group.add_argument(
        '--studconfig-file',
        dest='studconfig_file',
        default=None,
        required=has_move_arg,
    )
    arg_group.add_argument(
        '--studie-progs-file',
        dest='studieprogs_file',
        default=None,
        required=has_move_arg,
    )
    arg_group.add_argument(
        '--student-info-file',
        dest='student_info_file',
        default=None,
        required=has_move_arg,
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()

    Cerebrum.logutils.autoconf('bofhd_req', args)
    DEBUG = args.debug

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Utils.Factory.get('Database')()
    db.cl_init(change_program='process_bofhd_r')
    const = constants_cls(db)

    if args.process:
        if has_move_arg:
            logger.info('Processing move requests')
            # Asserting that a legal value is assigned to args.ou_perspective
            args.ou_perspective = get_constant(db, parser, const.OUPerspective,
                                               args.ou_perspective)
            spread = const.get_constant(const.Spread, default_spread)
            msp = process_requests.MoveStudentProcessor(
                db,
                const,
                args.ou_perspective,
                args.emne_info_file,
                args.studconfig_file,
                args.studieprogs_file,
                default_spread=spread,
            )
            # Convert move_student requests into move_user requests
            msp.process_requests(args.student_info_file)

        logger.info('Processing regular requests')
        rp = process_requests.RequestProcessor(db, const)
        rp.process_requests(operations_map, args.types, args.max_requests)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
