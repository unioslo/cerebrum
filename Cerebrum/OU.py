# Copyright 2002 University of Oslo, Norway
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

"""

from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityPhone, EntityAddress


ENTITY_TYPE_OU = 'o'


class OUStructure(object):
    "Mixin class, used by OU for OUs with structure."

    def set_parent(self, perspective, parent_id):
        "Set the parent of this OU to `parent_id' in `perspective'."
        self.execute("""
        INSERT INTO cerebrum.ou_structure (ou_id, perspective, parent_id)
        VALUES (:1, :2, :3)""", self.entity_id, perspective, parent_id)

    def get_structure_mappings(self, perspective):
        "Return a list of ou_id -> parent_id mappings reperesenting the ou structure."
        return self.query("""
        SELECT ou_id, parent_id FROM cerebrum.ou_structure
        WHERE perspective=:1""", perspective)

class OU(Entity, EntityContactInfo, EntityPhone, EntityAddress, OUStructure):

    def new(self, name, acronym=None, short_name=None, display_name=None,
            sort_name=None):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """

        new_id = super(OU, self).new(ENTITY_TYPE_OU)
        self.execute("""
        INSERT INTO cerebrum.ou_info (entity_type, ou_id, name, acronym,
                                      short_name, display_name, sort_name)
        VALUES (:1, :2, :3, :4, :5, :6, :7)""", ENTITY_TYPE_OU, new_id,
                     name, acronym, short_name, display_name, sort_name)
        return new_id

    def find(self, ou_id):
        """Associate the object with the OU whose identifier is OU_ID.

        If OU_ID isn't an existing OU identifier,
        NotFoundError is raised.

        """
        self.ou_id, self.name, self.acronym, self.short_name, self.display_name, self.sort_name = self.query_1("""
        SELECT ou_id, name, acronym, short_name, display_name, sort_name
        FROM cerebrum.ou_info
        WHERE ou_id=:1""", ou_id)
