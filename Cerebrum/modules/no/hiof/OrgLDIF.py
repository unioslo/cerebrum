# -*- coding: utf-8 -*-
#
# Copyright 2007-2020 University of Oslo, Norway
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
from __future__ import unicode_literals

import logging

from Cerebrum.modules.OrgLDIF import OrgLdifGroupMixin

logger = logging.getLogger(__name__)


class HiofOrgLdifGroupMixin(OrgLdifGroupMixin):

    person_memberof_attr = 'hiofMemberOf'
    person_memberof_class = 'hiofMembership'


# TODO: Rename to HiofOrgLdif or something that *doesn't* cause N801
# TODO: Why doesn't hiof use norEduOrgLdif?


class hiofLDIFMixin(HiofOrgLdifGroupMixin):  # noqa: N801

    def init_person_addresses(self):
        # No snail mail addresses for persons.
        self.addr_info = {}
