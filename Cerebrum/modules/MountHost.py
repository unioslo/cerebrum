# -*- coding: iso-8859-1 -*-
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

"""MountDisk is a class for mapping a user homedisk to a different logon server. As is the case with Samba connections"""

import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum import Constants
from Cerebrum.Disk import Host
from Cerebrum.Utils import Factory

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)

class MountHost(Host):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('mount_type','mount_name','mount_host_id',)

    def clear(self):
        self.__super.clear()
        self.clear_class(MountHost)
        self.__updated = []

    def find(self, host_id):
        """Associate the object with MountHost whose identifier is 
	mount_host_id. If mount_host_id isn't an existing ID identifier,
        NotFoundError is raised."""
        self.__super.find(host_id)
        (self.mount_host_id, self.mount_type, self.mount_name) = self.query_1("""
        SELECT mount_host_id, mount_type, mount_name
        FROM [:table schema=cerebrum name=mount_host]
        WHERE mount_host_id=:m_host_id""", {'m_host_id': self.entity_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

# arch-tag: 4bdd1435-a85a-4d9d-85df-bf9d91e6261b
