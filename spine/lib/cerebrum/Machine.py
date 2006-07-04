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

from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError

from Disk import Host
from Types import CodeType

#magic incantation; explanation _SHOULD_ be provided at a later date.
__all__ = ['Machine', 'CpuArch', 'OperatingSystem', 'Interconnect']


table = 'cpu_arch_code'
class CpuArch(CodeType):
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


table = 'operating_system_code'
class OperatingSystem(CodeType):
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


table = 'interconnect_code'
class Interconnect(CodeType):
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


#define and register additional variables.

table = 'machine_info'
attrs = [
    DatabaseAttr('cpu_arch', table, CpuArch, write=True, optional=False),
    DatabaseAttr('operating_system', table, OperatingSystem, write=True, optional=False),
    DatabaseAttr('interconnect', table, Interconnect, write=True, optional=False),
    DatabaseAttr('total_memory', table, int, write=True, optional=True),
    DatabaseAttr('node_number', table, int, write=True, optional=True),
    DatabaseAttr('node_memory', table, int, write=True, optional=True),
    DatabaseAttr('node_disk', table, int, write=True, optional=True),
    DatabaseAttr('cpu_core_number', table, int, write=True, optional=True),
    DatabaseAttr('cpu_core_mflops', table, int, write=True, optional=True),
    DatabaseAttr('cpu_mhz', table, int, write=True, optional=True),
    
]

for attr in attrs:
    Host.register_attribute(attr)

#define aliases - that is attributes that are renamed in Spine
Host.db_attr_aliases[table] = {'id':'host_id'}

#define additional methods.
def is_machine(self):
    """Returns true if the object is a machine object"""
    try:
        return self.get_cpu_arch() is not None
    except NotFoundError, e:
        return False
    return True

is_machine.signature = bool

def promote_machine(self, cpu_arch, operating_system, interconnect):
    """Promote a host to machine"""
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Machine(self.get_database())
    p.populate(cpu_arch, operating_system, interconnect)
    p.write_db()

promote_machine.signature = None
promote_machine.signature_args = [CpuArch, OperatingSystem, Interconnect]
promote_machine.signature_write = True

def demote_machine(self):
    """Demote a machine to host"""

    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Machine(self.get_database())
    p.find(obj.entity_id)
    p.delete_machine()

demote_machine.signature = None
demote_machine.signature_write = True

#register ze newly defined methods
Host.register_methods([is_machine, promote_machine, demote_machine])
