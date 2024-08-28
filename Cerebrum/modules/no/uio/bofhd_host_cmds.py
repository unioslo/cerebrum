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
import logging
import textwrap

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd import bofhd_core
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import exc_to_text
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils
from Cerebrum.modules.bofhd_requests.request import BofhdRequests

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


def _get_host_disk_quota(host):
    """ Get default disk quota from disk host """
    const = host.const
    host_disk_quota = host.get_trait(const.trait_host_disk_quota)
    if host_disk_quota:
        return host_disk_quota['numval']
    return None


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
#
# Help texts
#


HELP_GROUP = {
    'host': "Host related commands",
    'misc': "Miscellaneous commands",
}

HELP_COMMANDS = {
    'host': {
        'host_info': 'Show information about a host',
    },
    'misc': {
        'misc_hadd': "Register a new host",
        'misc_hrem': "Remove a host",
        'misc_dadd': "Register a new disk",
        'misc_drem': "Remove a disk",
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
}
