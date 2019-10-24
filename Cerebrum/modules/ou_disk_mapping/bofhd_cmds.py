# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
This module contains ou_disk_mapping module commands for bofhd.

..warning::
    The classes in this module should *not* be used directly. Make subclasses
    of the classes here, and mix in the proper auth classes.

    E.g. given a ``FooAuth`` class that implements or overrides the core
    ``BofhdAuth`` authorization checks, you should create:
    ::

        class FooOuDiskMappingAuth(FooAuth, BofhdOUDiskMappingAuth):
            pass


        class FooOuDiskMappingCommands(BofhdOUDiskMappingCommands):
            authz = FooOuDiskMappingAuth

    Then list the FooOuDiskMappingCommands in your bofhd configuration file.
    This way, any override done in FooAuth (e.g. is_superuser) will also take
    effect in these classes.
"""
from __future__ import unicode_literals

import cereconf
import six
from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from .dbal import OUDiskMapping

no_access_error = PermissionDenied("Not allowed to access OU Settings")


class BofhdOUDiskMappingAuth(BofhdAuth):
    """Auth for ou_disk_mapping commands."""

    def can_modify_ou_path(self, operator, ou=None, query_run_any=False):
        """
        Check if an operator is allowed to set the homedir for an OU.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False

        raise no_access_error

    def can_list_ou_path(self, operator, ou=None, query_run_any=False):
        return self.can_modify_ou_path(operator, ou, query_run_any)

    def can_add_ou_path(self, operator, ou=None, query_run_any=False):
        return self.can_modify_ou_path(operator, ou, query_run_any)

    def can_remove_ou_path(self, operator, ou=None, query_run_any=False):
        return self.can_modify_ou_path(operator, ou, query_run_any)


HELP_GROUP = {}

HELP_CMD = {
    "ou": {
        "ou_homedir_add": "Add the homedir for an OU/aff/status combination",
        "ou_homedir_get": "Get the homedir for an OU/aff/status combination",
        "ou_homedir_remove":
            "Remove the homedir for an OU/aff/status combination",
    },
}

HELP_ARGS = {
    "aff": [
        "aff",
        "Enter affiliation",
        "The name of an affiliation, e.g STUDENT or STUDENT/aktiv",
    ],
    "path": [
        "path",
        "Enter path",
        "Path to a disk e.g /uio/kant/foo or entity id prepended by id:",
    ],
}


class BofhdOUDiskMappingCommands(BofhdCommandBase):
    """OU Disk Mapping commands."""

    all_commands = {}
    authz = BofhdOUDiskMappingAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            (HELP_GROUP, HELP_CMD, HELP_ARGS), get_help_strings()
        )

    def __find_ou(self, ou):
        # Try to find the OU the user wants to edit
        ou_class = self.OU_class(self.db)
        if ou.startswith("id:"):
            ou = ou[3:]
            # Assume we got the entity id of the ou
            try:
                ou_class.find(ou)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "Unknown OU id {}".format(six.text_type(ou))
                )
        elif len(ou) == 6:
            # Assume we got a stedkode
            fakultet = ou[:2]
            institutt = ou[2:4]
            avdeling = ou[4:]
            institusjon = cereconf.DEFAULT_INSTITUSJONSNR
            try:
                ou_class.find_stedkode(
                    fakultet, institutt, avdeling, institusjon
                )
            except Errors.NotFoundError:
                raise CerebrumError(
                    "Unknown OU with stedkode {}".format(six.text_type(ou))
                )
        else:
            raise CerebrumError(
                "Unable to parse OU id or stedkode {}".format(ou)
            )
        return ou_class

    #
    # ou homedir_set <path> <ou> <aff> <status>
    #
    all_commands["ou_homedir_add"] = Command(
        ("ou", "homedir_add"),
        SimpleString(help_ref="path"),
        SimpleString(help_ref="ou"),
        SimpleString(help_ref="aff", optional=True),
        fs=FormatSuggestion(
            "Set homedir='%s' for affiliation %s at OU %s",
            ("path", "aff", "ou"),
        ),
        perm_filter="can_add_ou_path",
    )

    def ou_homedir_add(self, operator, disk, ou, aff=None):
        """Set default home dir for aff at OU

        :param operator:
        :param str ou:
        :param str or None aff:
        :param str disk:
        :rtype: dict
        :return: client output
        """
        ou_class = self.__find_ou(ou)
        # Check if allowed to set default home dir for this Aff at this OU
        if not self.ba.can_add_ou_path(
            operator.get_entity_id(), ou_class.entity_id
        ):
            raise no_access_error

        # Try to find the Affiliation the user wants to edit
        aff_str = "*"
        if aff:
            try:
                aff, status = self.const.get_affiliation(aff)
            except Exception as e:
                raise CerebrumError(e)
            if status:
                aff_str = six.text_type(status)
                aff = status
            else:
                aff_str = six.text_type(aff)

        # Try to find the disk the users want to set
        disk_class = Factory.get("Disk")(self.db)
        if disk.startswith("id:") or disk.isdigit():
            # Assume this is an entity id
            try:
                disk_class.find(disk)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "Unknown disk with id {}".format(six.text_type(disk))
                )
        else:
            # Assume the user wrote a path
            try:
                disk_class.find_by_path(disk)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "Unknown disk with path {}".format(six.text_type(disk))
                )

        # Set the path and return some information to the user
        ous = OUDiskMapping(self.db)
        ous.add(ou_class.entity_id, aff, disk_class.entity_id)
        return {
            "ou": ou_class.entity_id,
            "aff": aff_str,
            "path": six.text_type(disk_class.path),
        }

    #
    # ou homedir_clear <ou> <aff> <status>
    #
    all_commands["ou_homedir_remove"] = Command(
        ("ou", "homedir_remove"),
        SimpleString(help_ref="ou"),
        SimpleString(help_ref="aff", optional=True),
        fs=FormatSuggestion(
            "Removed homedir for affiliation %s at OU %s",
            ("aff", "ou"),
        ),
        perm_filter="can_remove_ou_path",
    )

    def ou_homedir_remove(self, operator, ou, aff=None):
        """Remove default home dir for aff at OU

        If you want to remove the homedir for just the OU and any aff and
        status, use:
        > ou homedir_remove ou

        For OU with affiliation and wildcard status use:
        > ou homedir_remove ou aff

        For OU with affiliation and status use:
        > ou homedir_remove ou aff/status

        :param operator:
        :param str ou:
        :param str or None aff:
        :rtype: dict
        :return: client output
        """
        # Try to find the OU the user wants to edit
        ou_class = self.__find_ou(ou)

        # Check if allowed to clear home dir for this OU
        if not self.ba.can_remove_ou_path(
            operator.get_entity_id(), ou_class.entity_id
        ):
            raise no_access_error

        # Try to find the Affiliation the user wants to edit
        aff_str = "*"
        if aff:
            try:
                aff, status = self.const.get_affiliation(aff)
            except Exception as e:
                raise CerebrumError(e)
            if status:
                aff_str = six.text_type(status)
                aff = status
            else:
                aff_str = six.text_type(aff)

        # Clear the path and return some information to the user
        ous = OUDiskMapping(self.db)
        ous.delete(ou_class.entity_id, aff)
        return {
            "ou": ou_class.entity_id,
            "aff": aff_str,
        }

    #
    # ou homedir_get <ou> <aff> <status>
    #
    all_commands["ou_homedir_list"] = Command(
        ("ou", "homedir_list"),
        SimpleString(help_ref="ou"),
        SimpleString(help_ref="aff", optional=True),
        fs=FormatSuggestion(
            "%8s %12s %26s %s",
            ("stedkode", "ou", "aff", "disk"),
            hdr="%8s %12s %26s %s" % ("Stedkode", "Ou", "Affiliation", "Disk"),
        ),
        perm_filter="can_list_ou_path",
    )

    def ou_homedir_list(self, operator, ou, aff=None):
        """Get default home dir for aff at OU

        :param operator:
        :param str ou:
        :param str or None aff:
        :rtype: dict
        :return: client output
        """
        if aff is None:
            aff = NotSet

        # Try to find the OU the user wants to edit
        ou_class = self.__find_ou(ou)

        # Check if allowed to clear home dir for this OU
        if not self.ba.can_list_ou_path(
            operator.get_entity_id(), ou_class.entity_id
        ):
            raise no_access_error

        # Try to find the Affiliation the user wants to edit
        if aff:
            try:
                aff, status = self.const.get_affiliation(aff)
            except Exception as e:
                raise CerebrumError(e)
            if status:
                aff = status
        # Get the path and return some information to the user
        ous = OUDiskMapping(self.db)
        disk_class = Factory.get("Disk")(self.db)

        ret = []
        for row in ous.search(ou_class.entity_id, aff, any_status=True):
            if row["status_code"] is not None:
                aff_str = str(self.const.PersonAffStatus(row["status_code"]))
            elif row["aff_code"] is not None:
                aff_str = str(self.const.PersonAffiliation(row["aff_code"]))
            else:
                aff_str = None

            ou_class.clear()
            ou_class.find(row["ou_id"])
            # Get the stedkode of the OU if the stedkode module is present
            stedkode = (
                ou_class.get_stedkode()
                if hasattr(ou_class, "get_stedkode")
                else None
            )
            disk_class.clear()
            disk_class.find(row["disk_id"])
            ret.append(
                {
                    "stedkode": stedkode,
                    "ou": row["ou_id"],
                    "aff": aff_str,
                    "disk": disk_class.path,
                }
            )
        return ret
