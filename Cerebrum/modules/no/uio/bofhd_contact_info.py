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


class BofhdContactAuth(BaseAuth):
    """ Auth for entity contactinfo_* commands. """

    def can_get_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if (hasattr(cereconf, 'BOFHD_VOIP_ADMINS') and
                self.is_group_member(operator, cereconf.BOFHD_VOIP_ADMINS)):
                return True
        return super(BofhdContactAuth, self).can_get_contact_info(
            operator,
            entity=entity,
            contact_type=contact_type,
            query_run_any=query_run_any)


class BofhdContactInfo(BaseInfo):
    authz = BofhdContactAuth
