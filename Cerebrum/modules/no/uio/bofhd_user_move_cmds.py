# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
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
This module contains commands for moving users between disks.

These commands have their own command module, because they are (unneccessary)
complicated and *very* UiO-specific.

All of these commands used to be a part of `bofhd_uio_cmds`, but were extracted
into its own module at:

  Commit: 043c1ecca5ce02b0b8a725860d5b8e8d363d4520
  Merge:  ff08d65af eab6c7069
  Date:   Wed Aug 21 15:27:48 2024 +0200
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging
import re
import textwrap

import six

import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules.bofhd import bofhd_core
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import (Help, merge_help_strings)
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.disk_quota import DiskQuota
from Cerebrum.utils import date_compat
from Cerebrum.utils import email

from .bofhd_auth import UioAuth

logger = logging.getLogger(__name__)


class MoveType(cmd_param.Parameter):
    _type = 'moveType'
    _help_ref = 'move-type'


class MoveUserAuth(UioAuth):
    """ Auth for moving users.  """

    def can_move_user(self, operator, account=None, dest_disk=None,
                      query_run_any=False):
        """ Check if op can move user to a given destination disk. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return (
                self.can_give_user(operator, query_run_any=True)
                or self.can_receive_user(operator, query_run_any=True)
            )
        return (
            self.can_give_user(operator, account, query_run_any=query_run_any)
            and self.can_receive_user(operator, account, dest_disk,
                                      query_run_any=query_run_any)
        )

    def can_give_user(self, operator, account=None,
                      query_run_any=False):
        """ Check if op can remove an account from its current home disk. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator,
                self.const.auth_move_from_disk,
            )
        return self.has_privileged_access_to_account_or_person(
            operator,
            self.const.auth_move_from_disk,
            account,
        )

    def can_receive_user(self, operator, account=None, dest_disk=None,
                         query_run_any=False):
        """ Check if op is authorized to assign an account to a given disk. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator,
                self.const.auth_move_to_disk,
            )
        return self._query_disk_permissions(
            operator,
            self.const.auth_move_to_disk,
            dest_disk,
            account.entity_id,
        )


def _get_account_repr(account):
    """ Get a string representation of an account. """
    return "{} ({})".format(account.account_name, account.entity_id)


def _get_account_home(account, spread):
    """ Get homedir data for the account (to be moved). """
    try:
        return account.get_home(spread)
    except Errors.NotFoundError:
        raise CerebrumError(
            "Cannot move %s: account has no home"
            % (_get_account_repr(account),))


def _normalize_reason(reason):
    """ Get a valid, normalized bofhd request reason. """
    request_reason_max_len = 80
    reason = reason.strip()
    if len(reason) > request_reason_max_len:
        raise CerebrumError(
            "Invalid move request reason - max length: "
            + repr(request_reason_max_len))
    return reason


def _get_account_by_uid(db, uid):
    """ Look up posix account by uid. """
    account = Utils.Factory.get("PosixUser")(db)
    try:
        account.find_by_uid(int(uid))
        return account
    except ValueError:
        raise CerebrumError("Invalid uid: " + repr(uid))
    except Errors.NotFoundError:
        raise CerebrumError("Could not find account with uid="
                            + repr(uid))


def _send_batch_move_notification(account, new_disk):
    """
    Notify user about their new homedir path.

    This is done for `user move batch`.
    """
    new_homedir = new_disk.path + '/' + account.account_name
    try:
        email.mail_template(
            account.get_primary_mailaddress(),
            cereconf.USER_BATCH_MOVE_WARNING,
            substitute={
                'USER': account.account_name,
                'TO_DISK': new_homedir,
            },
        )
    except Exception as e:
        logger.warning("Unable to notify %s (batch move): %s",
                       _get_account_repr(account), repr(e))


class MoveUserCommands(bofhd_core.BofhdCommandBase):
    """ Command and helpers for moving users between disks. """

    all_commands = {}
    authz = MoveUserAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        groups, cmds, args = merge_help_strings(
            (HELP_GROUP, {}, HELP_ARGS),
            bofhd_core_help.get_help_strings(),
            ({}, HELP_COMMANDS, {}),
        )
        # Add an extra, custom help category for `user move`
        groups.update(HELP_BASICS)
        return (groups, cmds, args)

    @property
    def home_spread(self):
        """ default spread for account homedir """
        return self.const.spread_uio_nis_user

    def _get_account(self, ident):
        """ Account lookup with support for uid:<posix-uid>. """
        if ":" in ident:
            id_type, id_value = ident.split(":", 1)
            if id_type == "uid":
                return _get_account_by_uid(self.db, id_value)

        # Default lookup (account name, account id)
        return super(MoveUserCommands, self)._get_account(ident)

    def _get_target_disk(self, account, ident):
        """ Disk lookup with a more suitable error message. """
        disk, disk_id, path = super(MoveUserCommands, self)._get_disk(
            path=ident,
            raise_not_found=False,
        )
        if disk_id is None:
            raise CerebrumError(
                "Cannot move %s: bad destination disk %s"
                % (_get_account_repr(account), repr(ident)))
        return disk

    #
    # user move prompt
    #
    def user_move_prompt_func(self, session, *args):
        """ user move prompt helper

        Base command:
          user move <move-type> <account-name>

        Variants:
          user move student           <move-account>
          user move student_immediate <move-account>
          user move confirm           <move-account>
          user move cancel            <move-account>

          user move immediate         <move-account> <move-disk>
          user move batch             <move-account> <move-disk>
          user move nofile            <move-account> <move-disk>
          user move hard_nofile       <move-account> <move-disk>

          user move request           <move-account> <move-disk> <move-reason>
        """
        help_struct = Help([self], logger=logger.getChild("_help"))
        help_move_type = MoveType(help_ref="move-type")
        help_account = cmd_param.AccountName(help_ref="move-account")
        help_disk = cmd_param.DiskId(help_ref="move-disk")
        help_path = cmd_param.DiskId(help_ref="move-path")
        help_reason = cmd_param.SimpleString(help_ref="move-reason")

        args = list(args)

        # check for move-type
        if not args:
            return help_move_type.get_struct(help_struct)
        move_type = args.pop(0)

        # check for account-name
        if not args:
            return help_account.get_struct(help_struct)
        args.pop(0)

        # final argument message
        last_value = {'last_arg': True}

        if move_type in ("student", "student_immediate",
                         "confirm", "cancel"):
            # move-type doesn't need more args
            return last_value

        if move_type in ("immediate", "batch", "nofile"):
            # # check for disk-id
            if not args:
                last_value.update(help_disk.get_struct(help_struct))
            return last_value

        if move_type in ("hard_nofile",):
            # # check for disk-id
            if not args:
                last_value.update(help_path.get_struct(help_struct))
            return last_value

        if move_type in ("request",):
            # check for disk-id
            if not args:
                return help_disk.get_struct(help_struct)
            args.pop(0)

            # check for reason
            if not args:
                last_value.update(help_reason.get_struct(help_struct))
            return last_value

        raise CerebrumError("Bad user_move command (%s)" % repr(move_type))

    #
    # user move <move-type> <account-name> [opts]
    #
    all_commands['user_move'] = cmd_param.Command(
        ("user", "move"),
        prompt_func=user_move_prompt_func,
        perm_filter="can_move_user",
    )

    def user_move(self, operator, move_type, accountname, *args):
        # now strip all str / unicode arguments in order to please CRB-2172
        args = tuple(
            (a.strip() if isinstance(a, six.string_types) else a)
            for a in args
        )
        logger.debug('user_move: after stripping args (%s)', args)
        account = self._get_account(accountname)

        if account.is_expired():
            raise CerebrumError(
                "Cannot move %s: account is expired"
                % (_get_account_repr(account),))

        if move_type == "immediate":
            return self._user_move_immediate(operator, account, *args)

        if move_type == "batch":
            return self._user_move_batch(operator, account, *args)

        if move_type == "nofile":
            return self._user_move_nofile(operator, account, *args)

        if move_type in ("hard_nofile",):
            return self._user_move_hard_nofile(operator, account, *args)

        if move_type == "student":
            return self._user_move_student(operator, account, *args)

        if move_type == "student_immediate":
            return self._user_move_student_immediate(operator, account, *args)

        if move_type == "confirm":
            return self._user_move_confirm(operator, account, *args)

        if move_type == "cancel":
            return self._user_move_cancel(operator, account, *args)

        if move_type in ("request",):
            return self._user_move_request(operator, account, *args)

        raise CerebrumError("Bad user_move command (%s)" % repr(move_type))

    def _user_move_immediate(self, operator, account, disk_ident):
        """ Move user in the next bofhd-request processing run.  """
        disk = self._get_target_disk(account, disk_ident)
        self.ba.can_move_user(operator.get_entity_id(), account, disk)

        ah = _get_account_home(account, self.home_spread)
        br = BofhdRequests(self.db, self.const)

        messages = self._get_move_warnings(account, disk, ah['homedir_id'])
        br.add_request(
            operator=operator.get_entity_id(),
            when=br.now,
            op_code=self.const.bofh_move_user_now,
            entity_id=account.entity_id,
            destination_id=int(disk.entity_id),
            state_data=int(self.home_spread),
        )
        messages.append("Command queued for immediate execution.")
        return "\n".join(messages)

    def _user_move_batch(self, operator, account, disk_ident):
        """ Move user in the regular, nightly bofhd-request processing run. """
        disk = self._get_target_disk(account, disk_ident)
        self.ba.can_move_user(operator.get_entity_id(), account, disk)

        ah = _get_account_home(account, self.home_spread)
        br = BofhdRequests(self.db, self.const)

        messages = self._get_move_warnings(account, disk, ah['homedir_id'])
        when = br.batch_time
        br.add_request(
            operator=operator.get_entity_id(),
            when=when,
            op_code=self.const.bofh_move_user,
            entity_id=account.entity_id,
            destination_id=int(disk.entity_id),
            state_data=int(self.home_spread),
        )
        messages.append("Move queued for execution at %s."
                        % (when.strftime("%Y-%m-%dT%H:%M:%S"),))
        # mail user about the awaiting move operation
        _send_batch_move_notification(account, disk)
        return "\n".join(messages)

    def _user_move_nofile(self, operator, account, disk_ident):
        """ Move user to a new path without actually moving anything. """
        disk = self._get_target_disk(account, disk_ident)
        self.ba.can_move_user(operator.get_entity_id(), account, disk)

        ah = _get_account_home(account, self.home_spread)
        messages = self._get_move_warnings(account, disk, ah['homedir_id'])
        if ah['disk_id'] is None:
            # If previously hard-coded, non-disk,
            # we need to re-set the home path
            extra = {'home': None}
        else:
            extra = {}
        account.set_homedir(current_id=ah['homedir_id'],
                            disk_id=int(disk.entity_id),
                            **extra)
        account.write_db()
        messages.append("User moved.")
        return "\n".join(messages)

    def _user_move_hard_nofile(self, operator, account, home_path):
        """ Move user to a hard-coded path. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may use hard_nofile")
        ah = _get_account_home(account, self.home_spread)
        try:
            account.set_homedir(current_id=ah['homedir_id'],
                                disk_id=None,
                                home=home_path)
        except ValueError as e:
            raise CerebrumError(e)
        return "OK, user moved to hardcoded homedir"

    def _user_move_student(self, operator, account):
        """
        Move student user in the regular, nightly bofhd-request processing run.

        Like `user move batch`, but we calculate the new disk from studconfig
        rules.
        """
        self.ba.can_give_user(operator.get_entity_id(), account)

        # check for existing home dir
        _get_account_home(account, self.home_spread)

        br = BofhdRequests(self.db, self.const)
        when = br.batch_time
        br.add_request(
            operator=operator.get_entity_id(),
            when=when,
            op_code=self.const.bofh_move_student,
            entity_id=account.entity_id,
            destination_id=None,
            state_data=int(self.home_spread),
        )
        return ("student-move queued for execution at %s"
                % (when.strftime("%Y-%m-%dT%H:%M:%S"),))

    def _user_move_student_immediate(self, operator, account):
        """
        Move student user in the next bofhd-request processing run.

        Like `user move immediate`, but we calculate the new disk from
        studconfig rules.
        """
        self.ba.can_give_user(operator.get_entity_id(), account)

        # check for existing home dir
        _get_account_home(account, self.home_spread)

        br = BofhdRequests(self.db, self.const)
        br.add_request(
            operator=operator.get_entity_id(),
            when=br.now,
            op_code=self.const.bofh_move_student,
            entity_id=account.entity_id,
            destination_id=None,
            state_data=int(self.home_spread),
        )
        return "student-move queued for immediate execution"

    def _user_move_confirm(self, operator, account):
        """ Confirm existing move request for *account*. """
        self.ba.can_give_user(operator.get_entity_id(), account)
        br = BofhdRequests(self.db, self.const)
        r = br.get_requests(entity_id=int(account.entity_id),
                            operation=self.const.bofh_move_request)
        if not r:
            raise CerebrumError("No matching request found")
        br.delete_request(account.entity_id,
                          operation=self.const.bofh_move_request)
        # Flag as authenticated
        when = br.batch_time
        br.add_request(
            operator=operator.get_entity_id(),
            when=when,
            op_code=self.const.bofh_move_user,
            entity_id=account.entity_id,
            destination_id=r[0]['destination_id'],
            state_data=int(self.home_spread),
        )
        return ("move queued for execution at %s"
                % (when.strftime("%Y-%m-%dT%H:%M:%S"),))

    def _user_move_cancel(self, operator, account):
        """ Cancel any existing move requests for acocunt. """
        self.ba.can_give_user(operator.get_entity_id(), account)
        # TBD: Should superuser delete other request types as well?
        count = 0
        br = BofhdRequests(self.db, self.const)
        for tmp in br.get_requests(entity_id=int(account.entity_id)):
            if tmp['operation'] in (
                    self.const.bofh_move_student,
                    self.const.bofh_move_user,
                    self.const.bofh_move_give,
                    self.const.bofh_move_request,
                    self.const.bofh_move_user_now):
                count += 1
                br.delete_request(request_id=tmp['request_id'])
        return "OK, %d bofhd requests deleted" % (count,)

    def _user_move_request(self, operator, account, disk_ident, _reason):
        """
        Add a move request for *account*.

        This request must be *confirmed* by someone with access to move the
        account from its current homedir disk.
        """
        disk = self._get_target_disk(account, disk_ident)
        reason = _normalize_reason(_reason)
        self.ba.can_receive_user(operator.get_entity_id(), account, disk)

        # check for existing home dir
        _get_account_home(account, self.home_spread)

        br = BofhdRequests(self.db, self.const)
        br.add_request(
            operator=operator.get_entity_id(),
            when=br.now,
            op_code=self.const.bofh_move_request,
            entity_id=account.entity_id,
            destination_id=int(disk.entity_id),
            state_data=reason,
        )
        return "OK, request registered"

    #
    # Some helpers for `user move <immediate|batch|nofile>`
    #

    def _get_move_warnings(self, account, disk, homedir_id):
        """ Get a list of potential issues with moving *account* to *disk*. """
        return [
            warning
            for warning in (
                self._check_account_spreads(account, disk),
                self._check_disk_quota(account, disk, homedir_id),
            )
            if warning
        ]

    def _check_account_spreads(self, account, disk):
        """
        Check if the target disk is suitable for the given account spreads.

        :returns:
            A warning message if the target disk is not suitable for the
            account, otherwise `None`
        """
        # TODO: Are ifi disks and ifi-spreads a thing still?  This warning may
        # be obsolete...
        for r in account.get_spread():
            if (r['spread'] == self.const.spread_ifi_nis_user and
                    not re.match(r'^/ifi/', disk.path)):
                return ("WARNING: moving user with %s-spread to "
                        "a non-Ifi disk."
                        % six.text_type(self.const.spread_ifi_nis_user))
        return None

    def _check_disk_quota(self, account, disk, homedir_id):
        """
        Check if quota will be cleared by move.

        :returns:
            A warning message if the quota will be cleared, otherwise `None`
        """
        # TODO: Disk quotas have no real-world effect, so maybe we should just
        # remove this warning?
        has_dest_quota = disk.has_quota()
        default_dest_quota = disk.get_default_quota()
        current_quota = None
        dq = DiskQuota(self.db)
        try:
            dq_row = dq.get_quota(homedir_id)
        except Errors.NotFoundError:
            pass
        else:
            current_quota = dq_row['quota']
            if dq_row['quota'] is not None:
                current_quota = dq_row['quota']

            dq_expire = date_compat.get_date(dq_row['override_expiration'])
            days_left = ((dq_expire or datetime.date.min)
                         - datetime.date.today()).days
            if days_left > 0 and dq_row['override_quota'] is not None:
                current_quota = dq_row['override_quota']

        if current_quota is None:
            # this is OK
            pass
        elif not has_dest_quota:
            return ("Destination disk has no quota, so the current "
                    "quota (%d) will be cleared." % (current_quota,))
        elif current_quota <= default_dest_quota:
            return ("Current quota (%d) is smaller or equal to the "
                    "default at destination (%d), so it will be "
                    "removed." % (current_quota, default_dest_quota))
        return None


#
# Help texts
#


HELP_BASICS = {
    'user-move-info': textwrap.dedent(
        """
        Moving users
        ==============
        A common task is moving the home directory of a user account to
        another disk.

        This is usually done when a person gets an affiliation to a different
        org unit, and is (in most cases) a two-step process:

         1. Move an existing home directory to the correct disk/path.

         2. Update the home directory in Cerebrum, so that various target
            systems refers to the correct disk/path.

        Home directory moves are processed by a work queue, and the home
        directory value in Cerebrum will only get updated after a successful
        move.  Move requests are either scheduled as soon as possible (within
        minutes), or delayed for a nightly run.

        The basic command for this is `user move`:

        bofh> user move <move-type> <account-name> [move-args...]

        It accepts the following variants:

         1. immediate <move-account> <move-disk>
            Move home directory for <move-account> to <move-disk> as soon as
            possible.

         2. batch <move-account> <move-disk>
            Move home directory for <move-account> to <move-disk> during the
            next nightly processing.

            The targeted user is notified immediately (by email) about the
            scheduled move.

         3. nofile <move-account> <move-disk>
            Set home directory for <move-account> to <move-disk> without moving
            any existing home directory.

            Updates the home directory immediately.  Does not schedule home
            directory move.

            Since no action is done to move or otherwise create the new home
            directory, manual intervention is usually required on the disk
            host.

         4. hard_nofile <move-account> <move-path>
            Set home directory for <move-account> to a hard-coded <move-path>.

            Updates the home directory immediately.  Does not schedule home
            directory move.

            The existing home directory is not archived or cleaned up, so
            manual intervention is usually required if the user previously had
            a home directory on a disk known to Cerebrum.

         5. student <move-account>
            Move home directory for <move-account> to an appropriate student
            disk during the nightly processing.

            The target disk/path is calculated from rules in config.

         6. student_immediate <move-account>
            Move home directory for <move-account> to an appropriate student
            disk as soon as possible.

            The target disk/path is calculated from rules in config.

         7. request <move-account> <move-disk> <move-reason>
            Request moving <move-account> from it's current disk to
            <move-disk>.

            A disk owner of the current account homedir must confirm using
            `user move confirm <move-account>`.

         8. confirm <move-account>
            Confirm and queue existing move request for <move-account>.

            Home directory will be moved during the next nightly processing.

         9. cancel <move-account>
            Cancel all existing move requests for <move-account>.

        Examples:
        ::

            bofh> user move request
            Account to move > example
            Enter disk > /uio/kant/div-guest-u1
            Why? > Example
            OK, request registered

            bofh> user move confirm example
            move queued for execution at 2024-08-27T22:00:00
        """
    ).lstrip(),
}

HELP_GROUP = {
    # Probably not needed, but useful if the *user* category is
    # refactored/removed from the base class
    'user': "User related commands",
}

HELP_COMMANDS = {
    'user': {
        'user_move': (
            "Move a user home directory to another disk"
            " (`help user-move-info` for details)"
        ),
    },
}

HELP_ARGS = {
    'move-account': [
        "move-account",
        "Account to move",
        textwrap.dedent(
            """
            Enter an account name or id to move.

            Default lookups:

             - `<account-id>` (if numerical)
             - `<account-name>`

            Supported lookups:

             - `id:<account-id>`
             - `name:<account-name>
             - `uid:<posix-uid>`
            """
        ).lstrip(),
    ],
    'move-disk': [
        "move-disk",
        "New homedir disk",
        textwrap.dedent(
            """
            Enter the path to the new disk to use.

            Enter disk without a trailing slash, or username.

            Example:
                /usit/kant/div-guest-u1
            """
        ).lstrip(),
    ],
    'move-path': [
        "move-path",
        "New homedir path",
        textwrap.dedent(
            """
            Enter a hard-coded path to set as home directory.

            This value will be used as-is, and must include the username (if
            applicable), but without a trailing slash.

            The path will *not* be linked to existing Cerebrum disks, even if
            it refers to a valid Cerebrum disk.

            Example:
               /home/example-user
            """
        ).lstrip(),
    ],
    'move-reason': [
        "move-reason",
        "Why?",
        "Describe why this user should be moved (80 chars max)",
    ],
    'move-type': [
        'move-type',
        'Move type',
        textwrap.dedent(
            """
            Enter desired move type. Example: 'immediate'.

            Valid move types, and their required arguments:

             - immediate          <move-account> <move-disk>
             - batch              <move-account> <move-disk>
             - nofile             <move-account> <move-disk>
             - hard_nofile        <move-account> <move-path>
             - student            <move-account>
             - student_immediate  <move-account>
             - request            <move-account> <move-disk> <move-reason>
             - confirm            <move-account>
             - cancel             <move-account>

            See `help user-move-info` for details regarding the various move
            types, and moving users in general.  `help arg_help <argument>`
            offers more info about a required argument.
            """
        ).lstrip(),
    ],
}
