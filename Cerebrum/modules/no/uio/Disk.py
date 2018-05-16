# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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

from Cerebrum import Disk
from Cerebrum.Utils import Factory

class DiskUiOMixin(Disk.Disk):

    def get_default_quota(self):
        """Returns the quota, False if the disk has no quotas, or
        None if the disk has quota, but no default quota."""

        dquota = self.get_trait(self.const.trait_disk_quota)
        if dquota is None:
            return False
        if dquota['numval']:
            return dquota['numval']
        host = Factory.get("Host")(self._db)
        host.find(self.host_id)
        hquota = host.get_trait(self.const.trait_host_disk_quota)
        if hquota is None or hquota['numval'] is None:
            return None
        return hquota['numval']

