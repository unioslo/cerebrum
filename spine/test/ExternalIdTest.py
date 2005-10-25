# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
#

import unittest
from TestBase import *

class EntityExternalIdTest(SpineObjectTest):
    """Tests the external ID implementation in Spine."""

    def __find_available_stedkode_institusjon(self):
        s = self.tr.get_ou_searcher()
        l = [ou.get_institusjon() for ou in s.search()]
        i = 1
        while i in l:
            i += 1
        return i

    def __get_type_and_source_system(self):
        source_system = self.tr.get_source_system_searcher().search()[0]
        s = self.tr.get_entity_external_id_type_searcher()
        s.set_type(self.ou.get_type())
        result = s.search()
        assert len(result)
        return result[0], source_system

    def createObject(self):
        c = self.tr.get_commands()
        self.unique = 'unittest_%s' % id(self.tr)
        try:
            self.ou = c.create_ou(self.unique)
        except:
            institusjon = self.__find_available_stedkode_institusjon()
            self.ou = c.create_ou(self.unique, institusjon, 1, 1, 1)

    def deleteObject(self):
        self.ou.delete()

    def testExternalId(self):
        id_type, source_system = self.__get_type_and_source_system()
        self.ou.set_external_id(self.unique, id_type, source_system)
        assert self.unique == self.ou.get_external_id(id_type, source_system)
        assert self.unique in [i.get_external_id() for i in self.ou.get_external_ids()]
        fisk = self.ou.get_id()
        self.ou.set_external_id(self.unique + '2', id_type, source_system)
        assert len(self.ou.get_external_ids()) == 1
        assert self.unique + '2' == self.ou.get_external_id(id_type, source_system)
        assert self.unique + '2' in [i.get_external_id() for i in self.ou.get_external_ids()]

        self.ou.remove_external_id(id_type, source_system)
        assert not self.ou.get_external_ids()

if __name__ == '__main__':
    unittest.main()

# arch-tag: f96e88b8-4567-11da-8934-0e5586e9b0da
