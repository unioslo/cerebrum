# -*- coding: utf-8 -*-
# Copyright 2002, 2004 University of Oslo, Norway
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

"""MountDisk is a class for mapping a user homedisk to a different logon server. As is the case with Samba connections"""

import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum import Constants
from Cerebrum.Disk import Host
from Cerebrum.Utils import Factory


Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
Entity_class = Factory.get("Entity")


class MountHost(Host):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('mount_type','mount_type','mount_name','mount_host_id')

    def clear(self):
        self.__super.clear()
        self.clear_class(MountHost)
        self.__updated = []

    def find(self, host_id):
        """Associate the object with MountHost whose identifier is 
        mount_host_id. If mount_host_id isn't an existing ID identifier,
        NotFoundError is raised."""
        self.__super.find(host_id)
        (self.mount_host_id, self.mount_type, self.host_id, self.mount_name) = self.query_1("""
        SELECT mount_host_id, mount_type, host_id, mount_name
        FROM [:table schema=cerebrum name=mount_host]
        WHERE mount_host_id=:m_host_id""", {'m_host_id': self.entity_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def populate(self, mount_host_id, host_id, mount_name, mount_type=1, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_host)
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
        self.mount_host_id = mount_host_id
        self.host_id = host_id
	self.mount_name = mount_name
	self.mount_type = mount_type


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

            INSERT INTO [:table schema=cerebrum name=mount_host]
              (mount_host_id, mount_type, host_id, mount_name)
            VALUES (:m_h_id, :m_type, :h_id, :m_name)
                    """,
                         {'m_h_id': self.mount_host_id,
                          'm_type': self.mount_type,
                          'h_id': self.host_id,
                          'm_name': self.mount_name})



        else:
	    print("%s:%s:%s:%s" % (self.mount_host_id, self.mount_type, self.host_id, self.mount_name))
            self.execute("""
            UPDATE [:table schema=cerebrum name=mount_host]
            SET mount_type=:mount_type, host_id=:host_id, mount_name=:mount_name
            WHERE mount_host_id=:mount_host_id""",
                         {'mount_type': self.mount_type,
			  'mount_host_id': self.mount_host_id,
			  'host_id': self.host_id,
                          'mount_name': self.mount_name})

        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new



    def delete_mount(self):
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=mount_host]
            WHERE mount_host_id = :m_h_id""", {'m_h_id': self.entity_id})


    def list_all(self):
        return self.query("""
        SELECT mount_host_id, host_id, mount_name
        FROM [:table schema=cerebrum name=mount_host]""")


