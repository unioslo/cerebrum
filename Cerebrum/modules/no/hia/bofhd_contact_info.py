# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" This module contains contact_info related commands in bofhd. """
import cereconf

from Cerebrum.modules.bofhd.bofhd_contact_info import (
    BofhdContactAuth as BaseAuth,
    BofhdContactInfo as BaseInfo,
)
from Cerebrum.modules.bofhd.errors import PermissionDenied


class BofhdContactAuth(BaseAuth):
    """ Auth for entity contactinfo_* commands. """

    def can_add_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True

        # Users with auth_add_contactinfo can see and run command
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_add_contactinfo):
            # Only allow phone numbers to be added
            if contact_type is not None and contact_type not in (
                    self.const.contact_phone,
                    self.const.contact_phone_private,
                    self.const.contact_mobile_phone,
                    self.const.contact_private_mobile):
                raise PermissionDenied(
                    "You are only allowed to add phone numbers")
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to add contact info")

    def can_remove_contact_info(self, operator, entity_id=None,
                                contact_type=None, source_system=None,
                                query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # Users with auth_rem_contactinfo can see and run command
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_remove_contactinfo):
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to remove contact info")


class BofhdContactInfo(BaseInfo):
    authz = BofhdContactAuth
