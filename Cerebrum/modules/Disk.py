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

import cereconf
from Cerebrum.Entity import Entity


class Disk(Entity):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('host_id', 'path', 'description')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        for attr in Disk.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in Disk.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def populate(self, host_id, path, description):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_disk)
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
        self.host_id = host_id
        self.path = path
        self.description = description

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
            INSERT INTO [:table schema=cerebrum name=disk_info]
              (entity_type, host_id, disk_id, path, description)
            VALUES (:e_type, :host_id, :disk_id, :path, :description)
                    """,
                         {'e_type': int(self.const.entity_disk),
                          'host_id': self.host_id,
                          'disk_id': self.entity_id,
                          'path': self.path,
                          'description': self.description})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=disk_info]
            SET path=:path, descripiption=:description
            WHERE disk_id=:disk_id""",
                         {'path': self.path,
                          'description': self.description})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, OU)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.path == self.path) and
                     (other.description == self.description))
        if cereconf.DEBUG_COMPARE:
            print "Disk.__eq__ = %s" % identical
        return identical

    def find(self, disk_id):
        """Associate the object with the Disk whose identifier is disk_id.

        If disk_id isn't an existing Disk identifier,
        NotFoundError is raised."""
        self.__super.find(disk_id)
        (self.host_id, self.path, self.description) = self.query_1("""
        SELECT host_id, path, description
        FROM [:table schema=cerebrum name=disk_info]
        WHERE disk_id=:disk_id""", {'disk_id': disk_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

class Host(Entity):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'description')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        for attr in Host.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in Host.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def populate(self, name, description):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_host)
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
        self.description = description

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
            INSERT INTO [:table schema=cerebrum name=host_info]
              (entity_type, host_id, name, description)
            VALUES (:e_type, :host_id, :name, :description)
                    """,
                         {'e_type': int(self.const.entity_host),
                          'host_id': self.host_id,
                          'name': self.name,
                          'description': self.description})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=host_info]
            SET name=:name, descripiption=:description
            WHERE host_id=:host_id""",
                         {'name': self.name,
                          'description': self.description})
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
                     (other.description == self.description))
        if cereconf.DEBUG_COMPARE:
            print "Host.__eq__ = %s" % identical
        return identical

    def find(self, host_id):
        """Associate the object with the Host whose identifier is host_id.

        If host_id isn't an existing Host identifier,
        NotFoundError is raised."""
        self.__super.find(host_id)
        (self.host_id, self.name, self.description) = self.query_1("""
        SELECT host_id, name, description
        FROM [:table schema=cerebrum name=host_info]
        WHERE host_id=:host_id""", {'host_id': host_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False
