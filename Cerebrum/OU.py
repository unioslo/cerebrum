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

from Cerebrum import Utils
from Cerebrum.Entity import Entity, EntityContactInfo, EntityAddress


class OUStructure(object):
    """Mixin class, used by OU for OUs with structure."""

    def set_parent(self, perspective, parent_id):
        """Set the parent of this OU to ``parent_id`` in ``perspective``."""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=ou_structure]
          (ou_id, perspective, parent_id)
        VALUES (:e_id, :perspective, :parent_id)""",
                     {'e_id': self.entity_id,
                      'perspective': int(perspective),
                      'parent_id': parent_id})

    def get_structure_mappings(self, perspective):
        """Return list of ou_id -> parent_id connections in ``perspective``."""
        return self.query("""
        SELECT ou_id, parent_id
        FROM [:table schema=cerebrum name=ou_structure]
        WHERE perspective=:perspective""", {'perspective': int(perspective)})


class OU(OUStructure, EntityContactInfo, EntityAddress, Entity):

    # TODO: Eventually, this metaclass definition should be part of
    # the class definitions in Entity.py, but as that probably will
    # break a lot of code, we're starting here.
    __metaclass__ = Utils.mark_update

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'acronym', 'short_name', 'display_name',
                      'sort_name')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        for attr in OU.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in OU.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def populate(self, name, acronym=None, short_name=None,
                 display_name=None, sort_name=None, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_ou)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.name = name
        self.acronym = acronym
        self.short_name = short_name
        self.display_name = display_name
        self.sort_name = sort_name

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ou_info]
              (entity_type, ou_id, name, acronym, short_name, display_name,
               sort_name)
            VALUES (:e_type, :ou_id, :name, :acronym, :short_name, :disp_name,
                    :sort_name)""",
                         {'e_type': int(self.const.entity_ou),
                          'ou_id': self.entity_id,
                          'name': self.name,
                          'acronym': self.acronym,
                          'short_name': self.short_name,
                          'disp_name': self.display_name,
                          'sort_name': self.sort_name})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=ou_info]
            SET name=:name, acronym=:acronym, short_name=:short_name,
                display_name=:disp_name, sort_name=:sort_name
            WHERE ou_id=:ou_id""",
                         {'name': self.name,
                          'acronym': self.acronym,
                          'short_name': self.short_name,
                          'disp_name': self.display_name,
                          'sort_name': self.sort_name,
                          'ou_id': self.entity_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, OU)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.name == self.name) and
                     (other.acronym == self.acronym) and
                     (other.short_name == self.short_name) and
                     (other.display_name == self.display_name) and
                     (other.sort_name == self.sort_name))
        if self._debug_eq:
            print "OU.__eq__ = %s" % identical
        return identical

    def new(self, name, acronym=None, short_name=None, display_name=None,
            sort_name=None):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity."""
        OU.populate(self, name, acronym, short_name, display_name, sort_name)
        OU.write_db()
        return self.entity_id

    def find(self, ou_id):
        """Associate the object with the OU whose identifier is OU_ID.

        If OU_ID isn't an existing OU identifier,
        NotFoundError is raised."""
        self.__super.find(ou_id)
        (self.ou_id, self.name, self.acronym, self.short_name,
         self.display_name, self.sort_name) = self.query_1("""
        SELECT ou_id, name, acronym, short_name, display_name, sort_name
        FROM [:table schema=cerebrum name=ou_info]
        WHERE ou_id=:ou_id""", {'ou_id': ou_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False
