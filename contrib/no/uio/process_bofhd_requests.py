#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2016 University of Oslo, Norway
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

import mx
import pickle
import re
import socket
import ssl
import logging
import argparse

import cereconf

from Cerebrum import Utils
from Cerebrum import logutils
from Cerebrum import Errors
from Cerebrum.utils import json
from Cerebrum.modules import Email
from Cerebrum.modules import PosixGroup

from Cerebrum.utils.argutils import get_constant
from Cerebrum.modules.bofhd_requests import process_bofhd_requests

logger = logging.getLogger(__name__)

SSH_CMD = "/usr/bin/ssh"
SUDO_CMD = "sudo"
SSH_CEREBELLUM = [SSH_CMD, "cerebrum@cerebellum"]

DEBUG = False
EXIT_SUCCESS = 0

# TODO: now that we support multiple homedirs, we need to which one an
# operation is valid for.  This information should be stored in
# state_data, but for e-mail commands this column is already used for
# something else.  The proper solution is to change the databasetable
# and/or letting state_data be pickled.
db = Utils.Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Utils.Factory.get('CLConstants')(db)
const = Utils.Factory.get('Constants')(db)
default_spread = const.spread_uio_nis_user

operations_map = process_bofhd_requests.OperationsMap()


def get_email_server(account_id, local_db=db):
    """Return Host object for account's mail server."""
    et = Email.EmailTarget(local_db)
    et.find_by_target_entity(account_id)
    server = Email.EmailServer(local_db)
    server.find(et.email_server_id)
    return server


class CyrusConnectError(Exception):
    pass


def connect_cyrus(host=None, username=None, as_admin=True):
    """Connect to user's Cyrus and return IMAP object.  Authentication
    is always as CYRUS_ADMIN, but if as_admin is True (default),
    authorise as admin user, not username.

    It is assumed the Cyrus server accepts SASL PLAIN and SSL.
    """
    def auth_plain_cb(response):
        cyrus_pw = Utils.read_password(cereconf.CYRUS_ADMIN,
                                       cereconf.CYRUS_HOST)
        return "%s\0%s\0%s" % (username or cereconf.CYRUS_ADMIN,
                               cereconf.CYRUS_ADMIN, cyrus_pw)

    if as_admin:
        username = cereconf.CYRUS_ADMIN
    try:
        imapconn = Utils.CerebrumIMAP4_SSL(
            host=host.name,
            ssl_version=ssl.PROTOCOL_TLSv1)
    except socket.gaierror as e:
        raise CyrusConnectError("%s@%s: %s" % (username, host.name, e))
    try:
        imapconn.authenticate('PLAIN', auth_plain_cb)
    except (imapconn.error, socket.error) as e:
        raise CyrusConnectError("%s@%s: %s" % (username, host.name, e))
    return imapconn


@operations_map(const.bofh_email_create, delay=0)
def proc_email_create(r):
    es = None
    if r['destination_id']:
        es = Email.EmailServer(db)
        es.find(r['destination_id'])
    return cyrus_create(r['entity_id'], host=es)


@operations_map(const.bofh_email_delete, delay=4*60)
def proc_email_delete(r):
    try:
        uname = get_account(r['entity_id']).account_name
    except Errors.NotFoundError:
        logger.error("bofh_email_delete: %d: user not found",
                     r['entity_id'])
        return False

    # The database contains the new host, so the id of the server
    # to remove from is passed in destination_id.
    server = Email.EmailServer(db)
    try:
        server.find(r['destination_id'])
    except Errors.NotFoundError:
        logger.error("bofh_email_delete: %d: target server not found",
                     r['destination_id'])
        return False
    account = get_account(r['entity_id'])
    # If the account is deleted, we assume that delete_user has
    # already bumped the generation.  Otherwise, we bump the
    # generation ourselves
    generation = account.get_trait(const.trait_account_generation)
    update_gen = False
    if generation:
        generation = generation['numval']
    else:
        generation = 0
    if not account.is_deleted():
        generation += 1
        update_gen = True
    if cyrus_delete(server, uname, generation):
        if update_gen:
            account.populate_trait(const.trait_account_generation,
                                   numval=generation)
            account.write_db()
        return True
    else:
        return False


def cyrus_create(user_id, host=None):
    try:
        uname = get_account(user_id).account_name
    except Errors.NotFoundError:
        logger.error("cyrus_create: %d not found", user_id)
        return False
    if host is None:
        host = get_email_server(user_id)
    if not (cereconf.DEBUG_HOSTLIST is None or
            host.name in cereconf.DEBUG_HOSTLIST):
        logger.info("cyrus_create(%s, %s): skipping", uname, host.name)
        return False

    try:
        cyradm = connect_cyrus(host=host, username=uname)
        cyr = connect_cyrus(host=host, username=uname, as_admin=False)
    except CyrusConnectError, e:
        logger.error("cyrus_create: %s", e)
        return False
    status = True
    for sub in ("", ".spam", ".Sent", ".Drafts", ".Trash", ".Templates"):
        res, folders = cyradm.list('user.', pattern=uname + sub)
        if res == 'OK' and folders[0]:
            continue
        mbox = 'user.%s%s' % (uname, sub)
        res, msg = cyradm.create(mbox)
        if res != 'OK':
            logger.error("IMAP create %s failed: %s", mbox, msg)
            status = False
            break
        res, msg = cyr.subscribe(mbox)
        if res != 'OK':
            # We don't consider this fatal, but we want to know about
            # problems.
            logger.warn("IMAP subscribe %s failed: %s", mbox, msg)
    else:
        logger.debug("cyrus_create: %s successful", uname)
    cyradm.logout()
    cyr.logout()
    return status


def cyrus_delete(host, uname, generation):
    if not (cereconf.DEBUG_HOSTLIST is None or
            host.name in cereconf.DEBUG_HOSTLIST):
        logger.info("cyrus_delete(%s, %s): skipping", uname, host.name)
        return False
    # Backup Cyrus data before deleting it.
    if not archive_cyrus_data(uname, host.name, generation):
        logger.error("bofh_email_delete: Archival of Cyrus data failed.")
        return False
    try:
        cyradm = connect_cyrus(host=host)
    except CyrusConnectError, e:
        logger.error("bofh_email_delete: %s: %s" % (host.name, e))
        return False
    res, listresp = cyradm.list("user.", pattern=uname)
    if res != 'OK' or listresp[0] is None:
        logger.error("bofh_email_delete: %s: no mailboxes", uname)
        cyradm.logout()
        return True
    folders = ["user.%s" % uname]
    res, listresp = cyradm.list("user.%s." % uname)
    if res == 'OK' and listresp[0]:
        for line in listresp:
            m = re.match(r'^\(.*?\) ".*?" "?([^"]+)"?$', line)
            if not m:
                logger.error("bofh_email_delete: invalid folder name: %s",
                             line)
            folders += [m.group(1), ]
    # Make sure the subfolders are deleted first by reversing the
    # sorted list.
    folders.sort()
    folders.reverse()
    for folder in folders:
        logger.debug("deleting %s ... ", folder)
        cyradm.setacl(folder, cereconf.CYRUS_ADMIN, 'c')
        res = cyradm.delete(folder)
        if res[0] != 'OK':
            logger.error("IMAP delete %s failed: %s", folder, res[1])
            cyradm.logout()
            return False
    cyradm.logout()
    return True


def archive_cyrus_data(uname, mail_server, generation):
    args = [
        SUDO_CMD, cereconf.ARCHIVE_MAIL_SCRIPT,
        '--server', mail_server,
        '--user', uname,
        '--gen', str(generation)
    ]
    if DEBUG:
        args.append('--debug')
    cmd = SSH_CEREBELLUM + [" ".join(args), ]
    return (
        Utils.spawn_and_log_output(cmd, connect_to=[mail_server]) ==
        EXIT_SUCCESS)


@operations_map(const.bofh_sympa_create, delay=2*60)
def proc_sympa_create(request):
    """Execute the request for creating a sympa mailing list.

    @type request: ??
    @param request:
      An object describing the sympa list creation request.
    """

    try:
        listname = get_address(request["entity_id"])
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


@operations_map(const.bofh_sympa_remove, delay=2*60)
def proc_sympa_remove(request):
    """Execute the request for removing a sympa mailing list.

    @type request: ??
    @param request:
      A dict-like object containing all the parameters for sympa list
      removal.
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


def get_address(address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))


@operations_map(const.bofh_move_user, const.bofh_move_user_now, delay=24*60)
def proc_move_user(r):
    try:
        account, uname, old_host, old_disk = get_account_and_home(
            r['entity_id'], type='PosixUser',
            spread=r['state_data'])
        new_host, new_disk = get_disk(r['destination_id'])
    except Errors.NotFoundError:
        logger.error("move_request: user %i not found", r['entity_id'])
        return False
    if account.is_expired():
        logger.warn("Account %s is expired, cancelling request",
                    account.account_name)
        return False
    process_bofhd_requests.set_operator(db, r['requestee_id'])
    try:
        operator = get_account(r['requestee_id']).account_name
    except Errors.NotFoundError:
        # The mvuser script requires a valid address here.  We
        # may want to change this later.
        operator = "cerebrum"
    group = get_group(account.gid_id, grtype='PosixGroup')

    if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                 old_host, old_disk, new_host, new_disk, operator):
        logger.debug('user %s moved from %s to %s',
                     uname, old_disk, new_disk)
        ah = account.get_home(default_spread)
        account.set_homedir(current_id=ah['homedir_id'],
                            disk_id=r['destination_id'])
        account.write_db()
        return True
    else:
        return new_disk == old_disk


@operations_map(const.bofh_quarantine_refresh, delay=0)
def proc_quarantine_refresh(r):
    """process_changes.py has added bofh_quarantine_refresh for the
    start/disable/end dates for the quarantines.  Register a
    quarantine_refresh change-log event so that changelog-based
    quicksync script can revalidate the quarantines.

    """
    process_bofhd_requests.set_operator(db, r['requestee_id'])
    db.log_change(r['entity_id'], cl_const.quarantine_refresh, None)
    return True


@operations_map(const.bofh_archive_user, delay=2*60)
def proc_archive_user(r):
    spread = default_spread  # TODO: check spread in r['state_data']
    account, uname, old_host, old_disk = get_account_and_home(r['entity_id'],
                                                              spread=spread)
    operator = get_account(r['requestee_id']).account_name
    if delete_user(uname, old_host, '%s/%s' % (old_disk, uname),
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


@operations_map(const.bofh_delete_user, delay=2*60)
def proc_delete_user(r):
    spread = default_spread  # TODO: check spread in r['state_data']
    #
    # IVR 2007-01-25 We do not care if it's a posix user or not.
    # TVL 2013-12-09 Except that if it's a POSIX user, it should retain a
    #                personal file group.
    account, uname, old_host, old_disk = get_account_and_home(r['entity_id'],
                                                              spread=spread)
    if account.is_deleted():
        logger.warn("%s is already deleted" % uname)
        return True
    process_bofhd_requests.set_operator(db, r['requestee_id'])
    operator = get_account(r['requestee_id']).account_name
    et = Email.EmailTarget(db)
    try:
        et.find_by_target_entity(account.entity_id)
        es = Email.EmailServer(db)
        es.find(et.email_server_id)
        mail_server = es.name
    except Errors.NotFoundError:
        mail_server = ''

    if not delete_user(uname, old_host, '%s/%s' % (old_disk, uname),
                       operator, mail_server):
        return False

    account.expire_date = mx.DateTime.now()
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
    default_group = _get_default_group(account.entity_id)
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
                pu._set_owner_of_group(personal_fg)
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
            default_group = _get_default_group(account.entity_id)

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
    return True


def _get_default_group(account_id):
    try:
        # only posix_user-objects have a default group
        account = Utils.Factory.get('PosixUser')(db)
        account.clear()
        account.find(account_id)
    except Errors.NotFoundError:
        return None
    return account.gid_id


def delete_user(uname, old_host, old_home, operator, mail_server):
    account = get_account(name=uname)
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


def get_disk(disk_id):
    disk = Utils.Factory.get('Disk')(db)
    disk.clear()
    disk.find(disk_id)
    host = Utils.Factory.get('Host')(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path


def get_account(account_id=None, name=None, local_db=db):
    assert account_id or name
    acc = Utils.Factory.get('Account')(local_db)
    if account_id:
        acc.find(account_id)
    elif name:
        acc.find_by_name(name)
    return acc


def get_account_and_home(account_id, type='Account', spread=None):
    if type == 'Account':
        account = Utils.Factory.get('Account')(db)
    elif type == 'PosixUser':
        account = Utils.Factory.get('PosixUser')(db)
    account.clear()
    account.find(account_id)
    if spread is None:
        spread = default_spread
    uname = account.account_name
    try:
        home = account.get_home(spread)
    except Errors.NotFoundError:
        return account, uname, None, None
    if home['home'] is None:
        if home['disk_id'] is None:
            return account, uname, None, None
        host, home = get_disk(home['disk_id'])
    else:
        host = None  # TODO:  How should we handle this?
        home = home['home']
    return account, uname, host, home


def get_group(id, grtype="Group"):
    if grtype == "Group":
        group = Utils.Factory.get('Group')(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(id)
    return group


def main():
    global DEBUG

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--debug',
        dest='debug',
        action='store_true',
        help='Turn on debugging')
    parser.add_argument(
        '-t', '--type',
        dest='types',
        action='append',
        choices=['email', 'sympa', 'move', 'quarantine', 'delete'],
        required=True)
    parser.add_argument(
        '-m', '--max',
        dest='max_requests',
        default=999999,
        help='Perform up to this number of requests',
        type=int)
    parser.add_argument(
        '-p', '--process',
        dest='process',
        action='store_true',
        help='Perform the queued operations')
    args, _rest = parser.parse_known_args()

    has_move_arg = 'move' in args.types
    arg_group = parser.add_argument_group('Required for move_student requests')
    arg_group.add_argument(
        '--ou-perspective',
        dest='ou_perspective',
        default='perspective_fs'
    )
    arg_group.add_argument(
        '--emne-info-file',
        dest='emne_info_file',
        default=None,
        required=has_move_arg
    )
    arg_group.add_argument(
        '--studconfig-file',
        dest='studconfig_file',
        default=None,
        required=has_move_arg
    )
    arg_group.add_argument(
        '--studie-progs-file',
        dest='studieprogs_file',
        default=None,
        required=has_move_arg
    )
    arg_group.add_argument(
        '--student-info-file',
        dest='student_info_file',
        default=None,
        required=has_move_arg
    )

    logutils.options.install_subparser(parser)
    args = parser.parse_args()
    logutils.autoconf('bofhd_req', args)

    DEBUG = args.debug

    logger.info('Start of script %s', parser.prog)
    logger.debug('args: %r', args)

    if args.process:
        if has_move_arg:
            # Asserting that a legal value is assigned to args.ou_perspective
            args.ou_perspective = get_constant(db, parser, const.OUPerspective,
                                               args.ou_perspective)
            msp = process_bofhd_requests.MoveStudentProcessor(
                db,
                const,
                default_spread=default_spread
            )
            # Convert move_student requests into move_user requests
            msp.process_requests(
                args.ou_perspective,
                args.emne_info_file,
                args.studconfig_file,
                args.studieprogs_file,
                args.student_info_file
            )

        rp = process_bofhd_requests.RequestProcessor(db, const)
        rp.process_requests(operations_map, args.types, args.max_requests)



if __name__ == '__main__':
    main()
