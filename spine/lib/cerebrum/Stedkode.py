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

import Cerebrum.Errors
from Cerebrum.Utils import Factory

from CerebrumClass import CerebrumDbAttr
from Commands import Commands
from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.SpineExceptions import AlreadyExistsError

from OU import OU

# Convert katalog_merke to be inserted into db.
def ct(value):
    if value:
        return 'T'
    else:
        return 'F'

# Convert katalog_merke into boolean from a string.
def cf(db, value):
    if value == 'T':
        return True
    else:
        return False

# Register additional attributes in the OU class if this module is used
table = 'stedkode'
OU.register_attribute(CerebrumDbAttr('landkode', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('institusjon', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('fakultet', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('institutt', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('avdeling', table, int, write=True))
OU.register_attribute(CerebrumDbAttr('katalog_merke', table, bool,
                                convert_from=cf, convert_to=ct, write=True))

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
    if not hasattr(obj, 'landkode'):
        raise NotFoundError('OU has no stedkode attributes.')
    return pad_with_zeros(obj.landkode, 3) + pad_with_zeros(obj.institusjon, 5) + \
        pad_with_zeros(obj.fakultet, 2) + pad_with_zeros(obj.institutt, 2) + \
        pad_with_zeros(obj.avdeling, 2)

get_stedkode.signature = str
OU.register_methods([get_stedkode])

def create_ou(self, name, institusjon, fakultet, institutt, avdeling):
    db = self.get_database()
    ou = Factory.get('OU')(db)
    try:
        ou.find_stedkode(fakultet, institutt, avdeling, institusjon)
        raise AlreadyExistsError('Could not create OU \'%s\', another OU with the same stedkode already exists.' % name)
    except Cerebrum.Errors.NotFoundError:
        ou.populate(name, fakultet, institutt, avdeling, institusjon)
        ou.write_db()
    return OU(db, ou.entity_id)

# Overwrite the OU create method to take additional arguments
create_ou.signature = OU
create_ou.signature_args = [str, int, int, int, int]
create_ou.signature_write = True
Commands.register_methods([create_ou])

# arch-tag: 975c6be6-e251-11d9-9880-98d92f1bc0af
