# -*- coding: utf-8 -*-
#
# Copyright 2006-2019 University of Oslo, Norway
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
from Cerebrum.modules.OrgLDIF import OrgLDIF


class IndigoLDIFMixin(OrgLDIF):

    def get_orgUnitUniqueID(self):
        rows = self.ou.get_external_id(id_type=self.const.externalid_orgnr)
        if len(rows) == 1:
            # FEIDE wants "NO" + org.number from <http://www.wis.no/nsr/>
            return "NO" + rows[0]['external_id']
        # If we have no unambiguous identifier to use for the org.unit ID,
        # take the entity_id for now.
        return "%d" % self.ou.entity_id
