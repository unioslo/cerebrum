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
     Entity, EntityContactInfo, EntityAddress

class OUStructure(object):
    "Mixin class, used by OU for OUs with structure."

    def set_parent(self, perspective, parent_id):
        "Set the parent of this OU to `parent_id' in `perspective'."
        self.execute("""
        INSERT INTO cerebrum.ou_structure (ou_id, perspective, parent_id)
        VALUES (:e_id, :perspective, :parent_id)""",
                     {'e_id' : self.entity_id, 'perspective' : int(perspective),
                      'parent_id' : parent_id})

    def get_structure_mappings(self, perspective):
        "Return a list of ou_id -> parent_id mappings reperesenting the ou structure."
        return self.query("""
        SELECT ou_id, parent_id FROM cerebrum.ou_structure
        WHERE perspective=:perspective""", {'perspective' : int(perspective)})

class OU(Entity, EntityContactInfo, EntityAddress, OUStructure):

    def clear(self):
        "Clear all attributes associating instance with a DB entity."

        self.name = None
        self.acronym = None
        self.short_name = None
        self.display_name = None
        self.sort_name = None
        EntityAddress.clear(self)
        super(OU, self).clear()

    def populate(self, name, acronym=None, short_name=None, display_name=None,
            sort_name=None):
        "Set instance's attributes without referring to the Cerebrum DB."

        self.name = name
        self.acronym = acronym
        self.short_name = short_name
        self.display_name = display_name
        self.sort_name = sort_name

        super(OU, self).populate(self.const.entity_ou)

        self.__write_db = True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        """Ovveride the == test for objects.

        Note that None != the empty string ''"""
        assert isinstance(other, OU)
        identical = super(OU, self).__eq__(other)
        if not identical:
            return identical

        identical = EntityAddress.__eq__(self, other)
        if self._debug_eq: print "EntityAddress.__eq__ = %s" % identical
        if not identical: return False

        identical = ((other.name == self.name) and
                     (other.acronym == self.acronym) and
                     (other.short_name == self.short_name) and
                     (other.display_name == self.display_name) and
                     (other.sort_name == self.sort_name))
        if self._debug_eq: print "OU.__eq__ = %s" % identical
        return identical

    def write_db(self, as_object=None):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If `as_object' isn't specified (or is None), the instance is
        written as a new entry to the Cerebrum database.  Otherwise,
        the object overwrites the Entity entry corresponding to the
        instance `as_object'.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method.

        """
        assert self.__write_db

        super(OU, self).write_db(as_object)
        ou_id = self.entity_id

        if as_object is None:
            # ou_id = super(OU, self).new(int(self.const.entity_ou))
            self.execute("""
            INSERT INTO cerebrum.ou_info (entity_type, ou_id, name, acronym,
                   short_name, display_name, sort_name)
            VALUES (:e_type, :ou_id, :name, :acronym, :short_name, :disp_name, :sort_name)""",
                         {'e_type' : int(self.const.entity_ou), 'ou_id' : ou_id,
                          'name' : self.name, 'acronym' : self.acronym,
                          'short_name' : self.short_name, 'disp_name' : self.display_name,
                          'sort_name' : self.sort_name})
        else:
            ou_id = as_object.ou_id
            
            self.execute("""
            UPDATE cerebrum.ou_info SET name=:name, acronym=:acronym,
                   short_name=:short_name, display_name=:disp_name, sort_name=:sort_name
            WHERE ou_id=:ou_id""", 
                         {'name' : self.name, 'acronym' : self.acronym,
                          'short_name' : self.short_name, 'disp_name' : self.display_name,
                          'sort_name' : self.sort_name, 'ou_id' : ou_id})

        EntityAddress.write_db(self, as_object)

        self.ou_id = ou_id
        self.__write_db = False

    def new(self, name, acronym=None, short_name=None, display_name=None,
            sort_name=None):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """


        OU.populate(self, name, acronym, short_name, display_name, sort_name)
        OU.write_db(self)
        OU.find(self, self.entity_id)

        return self.entity_id

    def find(self, ou_id):
        """Associate the object with the OU whose identifier is OU_ID.

        If OU_ID isn't an existing OU identifier,
        NotFoundError is raised.

        """
        self.ou_id, self.name, self.acronym, self.short_name, self.display_name, self.sort_name = self.query_1("""
        SELECT ou_id, name, acronym, short_name, display_name, sort_name
        FROM cerebrum.ou_info
        WHERE ou_id=:ou_id""", {'ou_id' : ou_id})
        super(OU, self).find(ou_id)
