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

from Cerebrum.modules.bofhd.bofhd_contact_info import (
    BofhdContactAuth as BaseAuth,
    BofhdContactInfo as BaseInfo,
)
from Cerebrum.modules.bofhd.errors import PermissionDenied


class BofhdContactAuth(BaseAuth):
    """ Auth for entity contactinfo_* commands. """

    def _can_any(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        raise PermissionDenied("Restricted to superusers")

    def can_get_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        return self._can_any(operator, query_run_any=query_run_any)

    def can_add_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        return self._can_any(operator, query_run_any=query_run_any)

    def can_remove_contact_info(self, operator,
                                entity=None,
                                contact_type=None,
                                source_system=None,
                                query_run_any=False):
        return self._can_any(operator, query_run_any=query_run_any)


class BofhdContactInfo(BaseInfo):
    authz = BofhdContactAuth
