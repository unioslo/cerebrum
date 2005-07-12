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

from Cerebrum.Utils import Factory
import Cerebrum.Database

from CerebrumClass import CerebrumDbAttr
from Commands import Commands
from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.SpineExceptions import DatabaseError

from OU import OU

# Register additional attributes in the OU class if this module is used
table = 'stedkode'
OU.register_attribute(CerebrumDbAttr('landkode', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('institusjon', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('fakultet', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('institutt', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('avdeling', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('katalog_merke', table, str, write=True))

OU.db_attr_aliases[table] = { 'id' : 'ou_id' }
OU.build_methods()
OU.build_search_class()

def pad_with_zeros(num, length):
    string = str(num)
    while len(string) < length:
        string = '0' + string
    return string

def get_stedkode(self):
    obj = self._get_cerebrum_obj()
    return pad_with_zeros(obj.landkode, 3) + pad_with_zeros(obj.institusjon, 5) + \
        pad_with_zeros(obj.fakultet, 2) + pad_with_zeros(obj.institutt, 2) + \
        pad_with_zeros(obj.avdeling, 2)

def create_ou(self, name, institusjon, fakultet, institutt, avdeling):
    db = self.get_database()
    ou = Factory.get('OU')(db)
    ou.populate(name, fakultet, institutt, avdeling, institusjon)
    try:
        ou.write_db()
    except Cerebrum.Database.IntegrityError, e:
        raise DatabaseError('Could not create OU \'%s\', another OU with the same primary key probably exists already.' % name)
    spine_ou = OU(ou.entity_id, write_locker=self.get_writelock_holder())
    return spine_ou

# Overwrite the OU create method to take additional arguments
Commands.register_method(Method('create_ou', OU, args=[('name', str), ('institusjon', int), ('fakultet', int),
    ('institutt', int), ('avdeling', int)], write=True), create_ou, overwrite=True)

OU.register_method(Method('get_stedkode', str, args=[]), get_stedkode)

# arch-tag: 975c6be6-e251-11d9-9880-98d92f1bc0af
