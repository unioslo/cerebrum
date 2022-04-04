# -*- coding: utf-8 -*-
#
# Copyright 2007-2022 University of Oslo, Norway
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
from Cerebrum.modules.feide.ldif_mixins import NorEduAuthnLevelMixin
from Cerebrum.modules.no.OrgLDIF import NorEduOrgLdifMixin
from Cerebrum.modules.no.OrgLDIF import NorEduSmsAuthnMixin
from Cerebrum.modules.no.OrgLDIF import OrgLdifEntitlementsMixin

logger = logging.getLogger(__name__)


# We inherit from NorEduOrgLdifMixin only to keep the MRO (and in turn
# objectClass values) in the same order they've been before refactors.
#
# This is only for easier diffing - it's not needed for any other purpose and
# could be removed.
class _HiofGroupMixin(OrgLdifGroupMixin, NorEduOrgLdifMixin):

    # Attributes and values for OrgLdifGroupMixin
    person_memberof_attr = 'hiofMemberOf'
    person_memberof_class = 'hiofMembership'


class HiofOrgLdif(_HiofGroupMixin,
                  OrgLdifEntitlementsMixin,
                  NorEduAuthnLevelMixin,
                  NorEduSmsAuthnMixin):

    def init_person_addresses(self):
        # No snail mail addresses for persons.
        self.addr_info = {}
