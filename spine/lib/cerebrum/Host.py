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

import Cerebrum.Database
from Cerebrum.Utils import Factory
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity, ValueDomainHack
from Types import EntityType
from Commands import Commands

from SpineLib import Registry
from SpineLib.SpineExceptions import ValueError
registry = Registry.get_registry()

__all__ = ['Host']

table = 'host_info'
class Host(Entity):
    slots = Entity.slots + (
        DatabaseAttr('name', 'entity_name', str, write=True),
        DatabaseAttr('description', table, str, write=True)
    )
    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'host_id'
    }
    db_constants = Entity.db_constants.copy()
    db_constants['entity_name'] = ValueDomainHack('host')

    cerebrum_class = Factory.get('Host')
    entity_type = 'host'

registry.register_class(Host)

def create(self, name, description):
    db = self.get_database()
    try:
        new_id = Host._create(db, name, description)
    except Cerebrum.Database.IntegrityError:
        raise ValueError('Invalid host name.')
    return Host(db, new_id)
create.signature = Host
create.signature_name = 'create_host'
create.signature_args = [str, str]
create.signature_write = True
create.signature_exceptions = [ValueError]

    
Commands.register_methods([create])

# arch-tag: bdad7df2-98cb-43f6-ab57-a9ae34a1c912
