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
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Builder import Method

from Entity import Entity
from Types import CodeType
from Commands import Commands
from Project import Project, ProjectAllocationName
from AllocationPeriod import AllocationAuthority, AllocationPeriod
from Host import Host
from Account import Account
from SpineLib.Date import Date

from SpineLib import Registry
registry = Registry.get_registry()


#magic incantation; explanation _SHOULD_ be provided at a later date.
#Basically, list all classes defined or modified in this file.

__all__ = ['Allocation', 'AllocationStatus']

#Define supporting classes

table = 'allocation_status_code'
#Denne må hete akkurat det samme som databasetabellen.
class AllocationStatus(CodeType):
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

table = 'allocation_credit_priority_code'
class AllocationCreditPriority(CodeType):
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
    
#We're defining a new class - thus this is the way to do it.
table = 'allocation_info' #('authority', 'name_id', 'period', 'status')
class Allocation(Entity):
    slots = Entity.slots + (
        DatabaseAttr('allocation_name', table, ProjectAllocationName, write=True, optional=False),
        DatabaseAttr('period', table, AllocationPeriod, write=True, optional=True),
        DatabaseAttr('status',table, AllocationStatus, write=True, optional=True)
    )
    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'allocation_id',
        'status':'allocation_status',
        'period':'allocation_period',
        'allocation_name':'name_id'
    }

    cerebrum_class = Factory.get('Allocation')
    entity_type = 'allocation'

registry.register_class(Allocation)

table = 'allocation_machine'
class AllocationMachine(DatabaseClass):
    primary = (
        DatabaseAttr('allocation', table, Allocation),
        DatabaseAttr('machine', table, Host)
    )
    db_attr_aliases = {
        table:{
            'allocation':'allocation_id',
        }
    }
registry.register_class(AllocationMachine)

table = 'credit_transaction'
class CreditTransaction(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('allocation', table, Allocation),
        DatabaseAttr('credits', table, int),
        DatabaseAttr('date', table, Date)
    )
    db_attr_aliases = {
        table:{
            'id':'credit_transaction_id',
            'allocation':'allocation_id'
        }
    }
registry.register_class(CreditTransaction)

table = 'allocation_transaction'
class AllocationTransaction(DatabaseClass):
    primary = (
        DatabaseAttr('credit_transaction', table, CreditTransaction),
    )
    slots = (
        DatabaseAttr('allocation_credit_priority', table, AllocationCreditPriority),
        DatabaseAttr('description', table, str)
    )
    db_attr_aliases = {
        table:{
            'credit_transaction':'credit_transaction_id',
        }
    }
registry.register_class(AllocationTransaction)

table = 'accounting_transaction'
class AccountingTransaction(DatabaseClass):
    primary = (
        DatabaseAttr('credit_transaction', table, CreditTransaction),
    )
    slots = (
        DatabaseAttr('jobsubmit', table, Date),
        DatabaseAttr('jobstart', table, Date),
        DatabaseAttr('jobend', table, Date),
        DatabaseAttr('machine', table, Host),
        DatabaseAttr('jobid', table, str),
        DatabaseAttr('jobname', table, str),
        DatabaseAttr('queuename', table, str),
        DatabaseAttr('num_nodes', table, int),
        DatabaseAttr('num_cores', table, int),
        DatabaseAttr('num_nodes_req', table, int),
        DatabaseAttr('num_cores_req', table, int),
        DatabaseAttr('memory_req_mb', table, int),
        DatabaseAttr('max_memory_mb', table, int),
        DatabaseAttr('walltime_req', table, int),
        DatabaseAttr('walltime', table, int),
        DatabaseAttr('cputime_req', table, int),
        DatabaseAttr('cputime', table, int),
        DatabaseAttr('waittime', table, int),
        DatabaseAttr('suspendtime', table, int),
        DatabaseAttr('num_suspends', table, int),
        DatabaseAttr('io_transfered_mb', table, int),
        DatabaseAttr('nice', table, int),
        DatabaseAttr('exitstatus', table, int),
        DatabaseAttr('account', table, Account)
    )
    db_attr_aliases = {
        table:{
            'credit_transaction':'credit_transaction_id',
        }
    }
registry.register_class(AccountingTransaction)

#define additional methods.

def create(self, authority, name_id, period, status):
    db = self.get_database()
    new_id = Allocation._create(db, authority, name_id, period, status)
    return Allocation(db, new_id)

create.signature = Allocation
create.signature_args = [ AllocationAuthority, ProjectAllocationName,
                          AllocationPeriod, AllocationStatus ]
create.signature_write = True
   
#register ze newly defined method
Commands.register_methods([create])
 
def add_machine(self, machine):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.add_machine(machine.get_id())
add_machine.signature = None
add_machine.signature_args = [Host]
add_machine.signature_write = True
Allocation.register_methods([add_machine])

def remove_machine(self, machine):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.remove_machine(machine.get_id())
remove_machine.signature = None
remove_machine.signature_args = [Host]
remove_machine.signature_write = True
Allocation.register_methods([remove_machine])

def get_machines(self):
    s = registry.AllocationMachineSearcher(self.get_database())
    s.set_allocation(self)
    return [i.get_machine() for i in s.search()]
get_machines.signature = [Host]
Allocation.register_methods([get_machines])
   
def get_allocations(self):
    s = registry.AllocationSearcher(self.get_database())
    s.set_allocation_name(self)
    return s.search()
get_allocations.signature = [Allocation]
ProjectAllocationName.register_methods([get_allocations])

