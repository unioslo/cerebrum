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

class OUStructure(object):
    "Mixin class, used by OU for OUs with structure."

    def add_structure_maping(self, perspective, parent_id):
        self.execute("""
    INSERT INTO cerebrum.ou_structure
      (ou_id, perspective, parent_id)
    VALUES (:1, :2, :3)""",
                     self.entity_id, perspective, parent_id)
    
class OU(Entity, EntityContactInfo, EntityPhone, EntityAddress, OUStructure):

    def new(self, name, acronym, short_name, display_name, sort_name):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.
        
        Note that the object is not automatically associated with the
        new entity.
        
        """
        
        new_id = super(OU, self).new('o')
        self.execute("""
        INSERT INTO cerebrum.ou_info(entity_type, ou_id, name, acronym, short_name,
           display_name, sort_name)
        VALUES (:1, :2, :3, :4, :5, :6, :7)""", 'o', new_id, name,
                    acronym, short_name, display_name, sort_name)
        return new_id

