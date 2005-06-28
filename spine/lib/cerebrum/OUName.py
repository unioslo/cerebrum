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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr, DatabaseError
from SpineLib.Builder import Method

from SpineLib import Registry

from OU import OU
from Types import LanguageType

registry = Registry.get_registry()

__all__ = ['OUName']

table = 'ou_name_language'
class OUName(DatabaseClass):
    primary = [
        DatabaseAttr('ou', table, OU),
        DatabaseAttr('language', table, LanguageType),
    ]
    slots = [
        DatabaseAttr('name', table, str, write=True),
        DatabaseAttr('acronym', table, str, write=True),
        DatabaseAttr('short_name', table, str, write=True), 
        DatabaseAttr('display_name', table, str, write=True),
        DatabaseAttr('sort_name', table, str, write=True)
    ]
    method_slots = []

    db_attr_aliases = {
        table : 
        {
            'ou': 'ou_id',
            'language': 'language_code',
        }
    }

registry.register_class(OUName)

# Create a method in OU for creating a new OUName.
# This method is strongly connected to the OU class,
# but defined here to avoid cyclic import problems.
def create_name(self, name, language):
    db = self.get_database()
    OUName._create(db, self.get_id(), language, name)
    n = OUName(self, language)
    return n
OU.register_method(Method('create_name', OUName, 
    args=[('name', str), ('language', LanguageType)], write=True),
    create_name)

