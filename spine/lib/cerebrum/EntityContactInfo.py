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

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import SourceSystem, ContactInfoType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityContactInfo']

table = 'entity_contact_info'

class EntityContactInfo(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('source_system', table, SourceSystem),
        DatabaseAttr('contact_type', table, ContactInfoType),
        DatabaseAttr('contact_pref', table, int)
    ]
    slots = [
        DatabaseAttr('contact_value', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntityContactInfo)

def get_contact_info(self):
    s = registry.EntityContactInfoSearcher(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_contact_info', [EntityContactInfo]), get_contact_info)

