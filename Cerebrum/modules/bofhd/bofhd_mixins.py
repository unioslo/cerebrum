# -*- coding: utf-8 -*-

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
"""
The bofhd.bofhd_mixins contains mixins that should go into the base
Group classes to support detection, deletion and cleanup of bofhd auth related
data.
"""
from Cerebrum.Group import Group


class BofhdAuthGroupMixin(Group):
    """
    This class is intended as a mixin to the base Group class, to enable
    identification and cleanup of BodhAuth related data.
    """
    # def __init__(self, database):
    #     super(BofhdAuthGroupMixin, self).__init__(database)

    def delete(self):
        """Removes all moderator rights for a group upon deletion"""
        self.execute(
            """
            DELETE FROM [:table schema=cerebrum name=auth_role]
            WHERE entity_id=:e_id
            """, {'e_id': self.entity_id})
