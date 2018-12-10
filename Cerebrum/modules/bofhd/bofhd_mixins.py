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
from Cerebrum.Entity import Entity
from Cerebrum.Utils import argument_to_sql


class BofhdAuthEntityMixin(Entity):
    """
    This class is intended as a mixin to the base Group class, to enable
    identification and cleanup of BofhdAuth related data.
    """
    # def __init__(self, database):
    #     super(BofhdAuthGroupMixin, self).__init__(database)

    def delete(self):
        """Removes all moderator rights for a group upon deletion, and removes
        moderator rights for other groups over this group."""
        # Delete entity from auth_role
        self.execute(
            """
            DELETE FROM [:table schema=cerebrum name=auth_role]
            WHERE entity_id=:e_id
            """, {'e_id': self.entity_id})
        # Find references to entity as op_target in auth_op_target
        target_list = self.query(
            """
            SELECT op_target_id
            FROM [:table schema=cerebrum name=auth_op_target]
            WHERE entity_id=:e_id
            """, {'e_id': self.entity_id})
        # If any references found, remove first from auth_role, then from
        # auth_op_target
        if target_list:
            op_target_id = [row['op_target_id'] for row in target_list]
            binds = dict()
            targets = argument_to_sql(op_target_id, "op_target_id", binds, int)
            # Delete entries from auth_role
            self.execute(
                """
                DELETE FROM [:table schema=cerebrum name=auth_role]
                WHERE %s """ % targets, binds)
            # Delete references to entity in auth_op_target
            self.execute(
                """
                DELETE FROM [:table schema=cerebrum name=auth_op_target]
                WHERE %s """ % targets, binds)
