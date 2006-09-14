# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

#import stuff

import Cerebrum.Errors
import Cerebrum.modules.Hpc

from Cerebrum.Utils import Factory
from SpineLib.DatabaseClass import DatabaseAttr

from Entity import Entity
from Types import CodeType
from Commands import Commands

from SpineLib.Date import Date
from SpineLib import Registry
registry = Registry.get_registry()


#magic incantation; explanation _SHOULD_ be provided at a later date.
#Basically, list all classes defined or modified in this file.

__all__ = ['AllocationPeriod', 'AllocationAuthority']

table = 'allocation_authority_code'
class AllocationAuthority(CodeType):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    )
    db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }

#We're defining a new Entity - thus this is the way to do it.
table = 'allocation_period' 
class AllocationPeriod(Entity):
    slots = Entity.slots + (
        DatabaseAttr('authority', table, AllocationAuthority, write=True, optional=False),
        DatabaseAttr('name', table, str, write=True, optional=False),
        DatabaseAttr('startdate', table, Date, write=True, optional=True),
        DatabaseAttr('enddate',table, Date, write=True, optional=True)
    )
    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'allocation_period_id'
    }

    cerebrum_class = Factory.get('AllocationPeriod')
    entity_type = 'allocationperiod'

registry.register_class(AllocationPeriod)


#define additional methods.

def create_allocation_period(self, authority, name, startdate, enddate):
    db = self.get_database()
    new_id = AllocationPeriod._create(db, authority.get_id(), name,
                startdate._value, enddate._value)
    return AllocationPeriod(db, new_id)

create_allocation_period.signature = AllocationPeriod
create_allocation_period.signature_args = [AllocationAuthority, str, Date, Date]
create_allocation_period.signature_write = True
Commands.register_methods([create_allocation_period])
