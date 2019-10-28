# -*- coding: utf-8 -*-
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
Mixins related to mod_ou_disk_mapping.
"""
from Cerebrum.Disk import Disk
from Cerebrum.OU import OU
from .dbal import OuDiskMapping


class OUMixin(OU):
    """
    OU mixin class that provides disk mapping cleanup.
    """

    def delete(self):
        """Delete any mappings to an OU."""
        ous = OuDiskMapping(self._db)
        for row in ous.get(ou_id=self.entity_id, aff_code=None,
                           status_code=None):
            ous.delete(ou_id=self.entity_id, aff_code=row['aff_code'],
                       status_code=row['status_code'])
        super(OUMixin, self).delete()


class DiskMixin(Disk):
    """
    Disk mixin class that provides disk mapping cleanup.
    """

    def delete(self):
        """Delete any mappings to a disk"""
        ous = OuDiskMapping(self._db)
        for row in ous.get_disk(disk_id=self.entity_id):
            ous.delete(ou_id=row['ou_id'], aff_code=row['aff_code'],
                       status_code=row['status_code'])
        super(DiskMixin, self).delete()
