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
This module contains host and disk related commands for bofhd.

Hosts and disks are closely related, so both objects share the same command
group.

Althrough hosts and disks are core objects in Cerebrum, these commands aren't
generic enough to be used in environments outside UiO.  This is partly because
disk removal is done through *BofhdRequests*, and because most commands
integrate with the ``Cerebrum.modules.disk_quota`` module.

Disk quotas are only "in use" at UiO.  Note that disk quotas through Cerebrum
aren't actually applied to the disk hosts or disks (or used for anything,
really).

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
import textwrap

import six

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd import bofhd_core
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import default_format_day as format_day
from Cerebrum.modules.bofhd.bofhd_utils import exc_to_text
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.disk_quota import DiskQuota
from Cerebrum.utils import date_compat

from .bofhd_auth import UioAuth

logger = logging.getLogger(__name__)


class DiskHostAuth(UioAuth):
    """
    Auth for various host and disk commands.

    Note:

    - Both creating and removing hosts are controlled by auth_create_host
    - Both creating and removing disks are controlled by auth_add_disk
    """

    def _can_modify_host(self, operator, query_run_any):
        if self.is_superuser(operator):
            return True
        # auth_create_host is not tied to a target
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_create_host):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_create_host(self, operator, query_run_any=False):
        """ Check if operator can create a host object. """
        return self._can_modify_host(operator, query_run_any=query_run_any)

    def can_remove_host(self, operator, host=None, query_run_any=False):
        """ Check if operator can remove a host object. """
        return self._can_modify_host(operator, query_run_any=query_run_any)

    def _can_modify_disk(self, operator, host, query_run_any):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator,
                self.const.auth_add_disk,
            )
        if host is not None:
            host = int(host.entity_id)
        if self._has_target_permissions(
                operator,
                self.const.auth_add_disk,
                self.const.auth_target_type_host,
                host,
                None):
            return True
        raise PermissionDenied("No access to host")

    def can_create_disk(self, operator, host=None, query_run_any=False):
        """ Check if operator can create a disk object. """
        return self._can_modify_disk(operator, host=host,
                                     query_run_any=query_run_any)

    def can_remove_disk(self, operator, host=None, disk=None,
                        query_run_any=False):
        """ Check if operator can remove a disk object. """
        return self._can_modify_disk(operator, host=host,
                                     query_run_any=query_run_any)

    def can_set_disk_quota(self, operator, account=None, unlimited=False,
                           forever=False, query_run_any=False):
        """ Check if op can override per-user disk quota. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_quota_set)
        if forever:
            self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_disk_quota_forever, account)
        if unlimited:
            self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_disk_quota_unlimited, account)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_disk_quota_set, account)

    def can_set_disk_default_quota(self, operator, host=None, disk=None,
                                   query_run_any=False):
        """ Check if op can set quota for disks or disk hosts. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_def_quota_set)
        if ((host is not None and self._has_target_permissions(
                                operator, self.const.auth_disk_def_quota_set,
                                self.const.auth_target_type_host,
                                host.entity_id, None)) or
            (disk is not None and self._has_target_permissions(
                                operator, self.const.auth_disk_def_quota_set,
                                self.const.auth_target_type_disk,
                                disk.entity_id, None))):
            return True
        raise PermissionDenied("No access to disk")

    def can_show_disk_quota(self, operator, account=None, query_run_any=False):
        """ Check if op can get disk quota/disk quota override for account. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_quota_show)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_disk_quota_show, account)


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


def _get_host_disk_quota(host):
    """ Get default disk quota from disk host """
    const = host.const
    host_disk_quota = host.get_trait(const.trait_host_disk_quota)
    if host_disk_quota:
        return host_disk_quota['numval']
    return None


def _get_disk_quota(disk):
    """ Get disk quota from disk """
    const = disk.const
    disk_trait = disk.get_trait(const.trait_disk_quota)
    if disk_trait is None:
        raise LookupError("no quota for disk id: " + repr(disk.entity_id))
    return disk_trait['numval']


def _calculate_disk_quota(disk, host_disk_quota):
    """ Calculate the actual disk quota, and a human readable hint. """
    try:
        disk_quota = _get_disk_quota(disk)
    except LookupError:
        # no disk quota trait - quota disabled
        disk_quota = None
        pretty_quota = "<none>"
    else:
        if disk_quota is None and host_disk_quota is None:
            # no disk quota - no host quota
            pretty_quota = "(no default)"
        elif disk_quota is None:
            # no disk quota - fallback to host quota
            disk_quota = host_disk_quota
            pretty_quota = "(%d MiB)" % (disk_quota,)
        else:
            # explicit disk quota
            pretty_quota = "%d MiB" % (disk_quota,)
    return (disk_quota, pretty_quota)


def _validate_disk_name(diskname):
    if not diskname.startswith("/"):
        raise CerebrumError("'%s' does not start with '/'" % (diskname,))

    if cereconf.VALID_DISK_TOPLEVELS is not None:
        toplevel_mountpoint = diskname.split("/")[1]
        if toplevel_mountpoint not in cereconf.VALID_DISK_TOPLEVELS:
            raise CerebrumError(
                "'%s' is not a valid toplevel mountpoint for disks"
                % (toplevel_mountpoint,))


class DiskHostCommands(bofhd_core.BofhdCommandBase):

    all_commands = {}
    authz = DiskHostAuth

    @property
    def util(self):
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            (HELP_GROUP, {}, HELP_ARGS),
            get_help_strings(),
            ({}, HELP_COMMANDS, {}),
        )

    def _get_account(self, ident):
        """ Account lookup with support for uid:<posix-uid>. """
        if ":" in ident:
            id_type, id_value = ident.split(":", 1)
            if id_type == "uid":
                return _get_account_by_uid(self.db, id_value)

        # Default lookup (account name, account id)
        return super(DiskHostCommands, self)._get_account(ident)

    # ###########################
    # ## Host related commands ##
    # ###########################

    #
    # host info <host>
    #
    all_commands['host_info'] = cmd_param.Command(
        ("host", "info"),
        cmd_param.SimpleString(help_ref='hostname'),
        fs=cmd_param.FormatSuggestion([
            ("Hostname:              %s\n"
             "Description:           %s",
             ("hostname", "desc")),
            ("Default disk quota:    %d MiB",
             ("def_disk_quota",))
        ]),
    )

    def host_info(self, operator, hostname):
        """ Show info on a *host* object. """
        host = self._get_host(hostname)
        ret = {
            'hostname': hostname,
            'desc': host.description
        }
        hquota = _get_host_disk_quota(host)
        if hquota:
            ret['def_disk_quota'] = hquota
        return ret

    #
    # misc hadd <hostname>
    #
    all_commands['misc_hadd'] = cmd_param.Command(
        # TODO: This should probably be ("host", "create")
        ("misc", "hadd"),
        cmd_param.SimpleString(help_ref="hostname"),
        perm_filter="can_create_host",
    )

    def misc_hadd(self, operator, hostname):
        """ Create a *host* object. """
        self.ba.can_create_host(operator.get_entity_id())
        host = Factory.get('Host')(self.db)
        # TODO: Should probably check if the host exists,
        # and raise a bofhd CerebrumError if it does
        host.populate(hostname, 'uio host')
        try:
            host.write_db()
        except self.db.DatabaseError as m:
            # TODO: We should probably validate the hostname before creating,
            #       and just not not handle this scenario
            raise CerebrumError("Database error: " + exc_to_text(m))

        host_data = {
            'entity_id': int(host.entity_id),
            'name': host.name,
            'description': host.description,
        }
        # TODO: Add FormatSuggestion, and return `host_data`
        return "OK, added host '%s'" % (host_data['name'],)

    #
    # misc hrem <hostname>
    #
    all_commands['misc_hrem'] = cmd_param.Command(
        # TODO: This should probably be ("host", "delete")
        ("misc", "hrem"),
        cmd_param.SimpleString(help_ref="hostname"),
        perm_filter="can_remove_host",
    )

    def misc_hrem(self, operator, hostname):
        """ Delete a *host* object. """
        host = self._get_host(hostname)
        self.ba.can_remove_host(operator.get_entity_id(), host=host)
        auth.delete_entity_auth_target(self.db, "host", int(host.entity_id))
        host_data = {
            'entity_id': int(host.entity_id),
            'name': host.name,
            'description': host.description,
        }
        try:
            host.delete()
        except self.db.DatabaseError as m:
            # TODO: We should probably not handle this scenario?
            raise CerebrumError("Database error: " + exc_to_text(m))

        # TODO: Add FormatSuggestion, and return `host_data`
        return "OK, %s deleted" % (host_data['name'],)

    # ###########################
    # ## Disk related commands ##
    # ###########################

    #
    # misc dadd <hostname> <disk-path>
    #
    all_commands['misc_dadd'] = cmd_param.Command(
        # TODO: This should probably be ("host", "disk_add")
        ("misc", "dadd"),
        cmd_param.SimpleString(help_ref="hostname"),
        cmd_param.DiskId(help_ref="diskname"),
        perm_filter="can_create_disk",
    )

    def misc_dadd(self, operator, hostname, diskname):
        """ Create a *disk* object. """
        host = self._get_host(hostname)
        self.ba.can_create_disk(operator.get_entity_id(), host=host)
        _validate_disk_name(diskname)

        disk = Factory.get('Disk')(self.db)
        disk.populate(host.entity_id, diskname, "uio disk")
        try:
            disk.write_db()
        except self.db.DatabaseError as m:
            # TODO: We should probably not handle this scenario?
            raise CerebrumError("Database error: " + exc_to_text(m))

        disk_data = {
            "host_id": int(host.entity_id),
            "hostname": host.name,
            "disk_id": int(disk.entity_id),
            "path": disk.path,
        }

        # TODO: Add FormatSuggestion, and return `disk_data`
        if len(diskname.split("/")) != 4:
            return "OK.  Warning: disk did not follow expected pattern."

        return ("OK, added disk '%s' at %s"
                % (disk_data['path'], disk_data['hostname']))

    #
    # misc drem <hostname> <disk-path>
    #
    all_commands['misc_drem'] = cmd_param.Command(
        # TODO: This should probably be ("host", "disk_remove")
        ("misc", "drem"),
        cmd_param.SimpleString(help_ref="hostname"),
        cmd_param.DiskId(help_ref="diskname"),
        perm_filter="can_remove_disk",
    )

    def misc_drem(self, operator, hostname, diskname):
        """ Remove a *disk* object. """
        host = self._get_host(hostname)
        disk = self._get_disk(diskname, host_id=int(host.entity_id))[0]

        self.ba.can_remove_disk(operator.get_entity_id(), host=host, disk=disk)

        # FIXME: We assume that all destination_ids are entities,
        # which would ensure that the disk_id number can't represent a
        # different kind of entity.  The database does not constrain
        # this, however.
        br = BofhdRequests(self.db, self.const)
        if br.get_requests(destination_id=disk.entity_id):
            raise CerebrumError(
                "There are pending requests. "
                "Use 'misc list_requests disk %s' to view them."
                % (diskname,))

        account = self.Account_class(self.db)
        for row in account.list_account_home(disk_id=int(disk.entity_id),
                                             filter_expired=False):
            if row['disk_id'] is None:
                continue
            if row['status'] == int(self.const.home_status_on_disk):
                raise CerebrumError(
                    "One or more users still on disk (e.g. %s)"
                    % (row['entity_name'],))

            account.clear()
            account.find(row['account_id'])
            ah = account.get_home(row['home_spread'])
            account.set_homedir(
                current_id=ah['homedir_id'],
                disk_id=None,
                home=account.resolve_homedir(
                    disk_path=row['path'],
                    home=row['home'],
                ),
            )
        auth.delete_entity_auth_target(self.db, "disk", int(disk.entity_id))
        disk_data = {
            "host_id": int(host.entity_id),
            "hostname": host.name,
            "disk_id": int(disk.entity_id),
            "path": disk.path,
        }
        try:
            disk.delete()
        except self.db.DatabaseError as m:
            # TODO: We should probably not handle this scenario?
            raise CerebrumError("Database error: " + exc_to_text(m))

        # TODO: Add FormatSuggestion, and return `disk_data`
        return "OK, %s deleted" % (disk_data['path'],)

    def _list_disks(self, host):
        hostname = host.name
        host_disk_quota = _get_host_disk_quota(host)

        disk = Factory.get("Disk")(self.db)
        disks = {}
        for row in disk.list(host.host_id):
            disk.clear()
            disk.find(row['disk_id'])

            def_quota, pretty_quota = _calculate_disk_quota(disk,
                                                            host_disk_quota)
            disks[row['disk_id']] = {
                'disk_id': row['disk_id'],
                'host_id': row['host_id'],
                'hostname': hostname,
                'def_quota': def_quota,
                'pretty_quota': pretty_quota,
                'path': row['path'],
            }
        ret = []
        for d in sorted(disks, key=lambda k: disks[k]['path']):
            ret.append(disks[d])
        return ret

    #
    # misc dls
    #
    # misc dls is deprecated, and can probably be removed without
    # anyone complaining much.
    #
    all_commands['misc_dls'] = cmd_param.Command(
        ("misc", "dls"),
        cmd_param.SimpleString(help_ref="hostname"),
        fs=cmd_param.get_format_suggestion_table(
            ("disk_id", "DiskId", 8, "d", False),
            ("host_id", "HostId", 8, "d", False),
            ("path", "Path", 32, "s", True),
        ),
    )

    def misc_dls(self, operator, hostname):
        """ List disks on a given *host*. """
        host = self._get_host(hostname)
        return self._list_disks(host)

    #
    # disk list
    #
    all_commands['disk_list'] = cmd_param.Command(
        # TODO: This should probably be ("host", "disk_list")
        ("disk", "list"),
        cmd_param.SimpleString(help_ref="hostname"),
        fs=cmd_param.get_format_suggestion_table(
            ("hostname", "Hostname", 13, "s", True),
            ("pretty_quota", "Default quota", 13, "s", True),
            ("path", "Path", 32, "s", True),
        ),
    )

    def disk_list(self, operator, hostname):
        """ List disks and default disk quotas on a given *host*. """
        host = self._get_host(hostname)
        return self._list_disks(host)

    # #################################
    # ## Disk quota related commands ##
    # #################################

    #
    # disk quota <host> <disk> <quota>
    #
    all_commands['disk_quota'] = cmd_param.Command(
        # TODO: This should probably be ("disk", "set_default_quota")
        ("disk", "quota"),
        cmd_param.SimpleString(help_ref="hostname"),
        cmd_param.DiskId(help_ref="diskname"),
        cmd_param.SimpleString(help_ref="dq-size"),
        perm_filter="can_set_disk_default_quota",
    )

    def disk_quota(self, operator, hostname, diskname, quota):
        """ Set default quota for a given *disk*. """
        host = self._get_host(hostname)
        disk = self._get_disk(diskname, host_id=host.entity_id)[0]
        self.ba.can_set_disk_default_quota(operator.get_entity_id(),
                                           host=host, disk=disk)
        old = disk.get_trait(self.const.trait_disk_quota)
        if quota.lower() == "none":
            if old:
                disk.delete_trait(self.const.trait_disk_quota)
            return "OK, no quotas on %s" % diskname
        elif quota.lower() == "default":
            disk.populate_trait(self.const.trait_disk_quota,
                                numval=None)
            disk.write_db()
            return "OK, using host default on %s" % diskname
        elif quota.isdigit():
            disk.populate_trait(self.const.trait_disk_quota,
                                numval=int(quota))
            disk.write_db()
            return "OK, default quota on %s is %d" % (diskname, int(quota))
        else:
            raise CerebrumError("Invalid quota value '%s'" % quota)

    #
    # host disk_quota <host> <quota>
    #
    all_commands['host_disk_quota'] = cmd_param.Command(
        # TODO: This should probably be ("host", "set_default_quota")
        ("host", "disk_quota"),
        cmd_param.SimpleString(help_ref="hostname"),
        cmd_param.SimpleString(help_ref="dq-size"),
        perm_filter="can_set_disk_default_quota",
    )

    def host_disk_quota(self, operator, hostname, quota):
        """ Set default quota for all disks on a given *host*. """
        host = self._get_host(hostname)
        self.ba.can_set_disk_default_quota(operator.get_entity_id(),
                                           host=host)
        old = host.get_trait(self.const.trait_host_disk_quota)
        if (quota.lower() == 'none' or
                quota.lower() == 'default' or
                (quota.isdigit() and int(quota) == 0)):
            # "default" doesn't make much sense, but the help text
            # says it's a valid value.
            if old:
                # TBD: disk is not defined here, what is this supposed to do?
                # disk.delete_trait(self.const.trait_disk_quota)
                raise Exception("does this ever happen?")
            return "OK, no default quota on %s" % hostname
        elif quota.isdigit() and int(quota) > 0:
            host.populate_trait(self.const.trait_host_disk_quota,
                                numval=int(quota))
            host.write_db()
            return "OK, default quota on %s is %d" % (hostname, int(quota))
        else:
            raise CerebrumError("Invalid quota value '%s'" % quota)

    #
    # user get_disk_quota
    #
    # This used to be in `user info`, but has been moved to a separate command
    #
    all_commands['user_get_disk_quota'] = cmd_param.Command(
        ("user", "get_disk_quota"),
        cmd_param.AccountName(help_ref="dq-account"),
        fs=cmd_param.FormatSuggestion([
            ("Username:      %s\n"
             "Home:          %s (status: %s)", ("username", "home",
                                                "home_status")),
            ("Disk quota:    %s MiB", ("disk_quota",)),
            ("DQ override:   %s MiB (until %s: %s)",
             ("dq_override", format_day("dq_expire"), "dq_why")),
        ]),
        perm_filter="can_show_disk_quota",
    )

    def user_get_disk_quota(self, operator, _account):
        """ Get quota override status for a given *account*. """
        account = self._get_account(_account)
        self.ba.can_show_disk_quota(operator.get_entity_id(), account)

        tmp = {
            'disk_id': None,
            'home': None,
            'status': None,
            'homedir_id': None,
        }
        try:
            tmp = dict(account.get_home(self.const.spread_uio_nis_user))
        except Errors.NotFoundError:
            pass
        if not tmp['disk_id']:
            raise CerebrumError("no homedir disk for " + account.account_name)

        tmp['home'] = account.resolve_homedir(disk_id=tmp['disk_id'],
                                              home=tmp['home'])

        ret = {
            'username': account.account_name,
            'home': tmp['home'],
            'home_status': (
                None if tmp['status'] is None
                else six.text_type(self.const.AccountHomeStatus(tmp['status']))
            ),
        }

        disk = Factory.get("Disk")(self.db)
        disk.find(tmp['disk_id'])
        has_quota = disk.has_quota()
        def_quota = disk.get_default_quota()
        try:
            dq = DiskQuota(self.db)
            dq_row = dq.get_quota(tmp['homedir_id'])
            if has_quota and dq_row['quota'] is not None:
                ret['disk_quota'] = str(int(dq_row['quota']))
            # Only display recent quotas
            dq_expire = date_compat.get_date(dq_row['override_expiration'])
            days_left = ((dq_expire or datetime.date.min)
                         - datetime.date.today()).days
            if days_left > -30:
                if dq_row['override_quota'] is not None:
                    dq_override_desc = dq_row['description']
                    if days_left < 0:
                        dq_override_desc += " [INACTIVE]"
                    ret.update({
                        'dq_override': str(int(dq_row['override_quota'])),
                        'dq_expire': dq_expire,
                        'dq_why': dq_override_desc,
                    })
        except Errors.NotFoundError:
            if def_quota:
                ret['disk_quota'] = "(%s)" % (def_quota,)
        return ret

    #
    # user set_disk_quota
    #
    all_commands['user_set_disk_quota'] = cmd_param.Command(
        ("user", "set_disk_quota"),
        cmd_param.AccountName(help_ref="dq-account"),
        cmd_param.Integer(help_ref="dq-override-size"),
        cmd_param.Date(help_ref="dq-expire-date"),
        cmd_param.SimpleString(help_ref="dq-reason"),
        perm_filter="can_set_disk_quota",
    )

    def user_set_disk_quota(self, operator, _account, _size, _date, _why):
        """ Set quota override for a given *account*. """
        account = self._get_account(_account)
        try:
            size = int(_size)
        except ValueError:
            raise CerebrumError("Invalid size: " + repr(_size))
        exp_date = parsers.parse_date(_date)
        why = _why.strip()
        if len(why) < 3:
            raise CerebrumError("Why cannot be blank")

        unlimited = forever = False
        if (exp_date - datetime.date.today()).days > 185:
            forever = True
        if size > 1024 or size < 0:    # "unlimited" for perm-check = +1024M
            unlimited = True
        self.ba.can_set_disk_quota(operator.get_entity_id(), account,
                                   unlimited=unlimited, forever=forever)
        home = account.get_home(self.const.spread_uio_nis_user)
        if size < 0:
            # unlimited disk quota
            size = None
        dq = DiskQuota(self.db)
        dq.set_quota(
            home['homedir_id'],
            override_quota=size,
            override_expiration=exp_date,
            description=why,
        )
        return "OK, quota overridden for %s" % (account.account_name,)


#
# Help texts
#


HELP_GROUP = {
    'disk': "Disk related commands",
    'host': "Host related commands",
    # Probably not needed, but useful if the *misc* or *user* categories are
    # refactored/removed from the base class:
    'misc': "Miscellaneous commands",
    'user': "User related commands",
}

HELP_COMMANDS = {
    'disk': {
        'disk_list': (
            "List the disks registered with a host.  A quota value in "
            "parenthesis means it uses to the host's default disk quota."
        ),
        'disk_quota': "Enable quotas on a disk, and set the default value",
    },
    'host': {
        'host_disk_quota': 'Set the default disk quota for a host',
        'host_info': 'Show information about a host',
    },
    'misc': {
        'misc_hadd': "Register a new host",
        'misc_hrem': "Remove a host",
        'misc_dadd': "Register a new disk",
        'misc_drem': "Remove a disk",
        'misc_dls': "Deprecated: use 'disk list'",
    },
    'user': {
        'user_set_disk_quota': 'Temporary override users disk quota',
        'user_get_disk_quota': 'Get disk quota/disk quota override for user',
    },
}

HELP_ARGS = {
    'hostname': [
        "hostname",
        "Enter a valid hostname",
        "Enter a hostname to create or look up.  Example: ulrik",
    ],
    'diskname': [
        "diskname",
        "Enter a disk path",
        textwrap.dedent(
            """
            Enter disk without a trailing slash.

            Example:
                /usit/kant/div-guest-u1
            """
        ).lstrip(),
    ],
    'dq-account': [
        "dq-account",
        "Enter an account",
        textwrap.dedent(
            """
            Enter an account name or id.

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
    "dq-expire-date": [
        "dq-expire-date",
        "Enter end-date for override",
        textwrap.dedent(
            """
            Expire date for disk quota override.  Format:

            {}
            """
        ).lstrip().format(parsers.parse_date_help_blurb),
    ],
    'dq-size': [
        'dq-size',
        'Enter disk quota (in MiB)',
        textwrap.dedent(
            """
            Enter quota size in MiB, or use none/default:

             - <n>:     set quota to <n> MiB
             - none:    disable quota
             - default: use the host's default quota
            """
        ).lstrip(),
    ],
    'dq-override-size': [
        'dq-override-size',
        'Enter disk quota (in MiB)',
        'Enter quota size in MiB, or -1 for unlimited quota',
    ],
    'dq-reason': [
        "dq-reason",
        "Why?",
        "Give a short reason why this quota override should exist",
    ],
}
