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
from SpineLib.DatabaseClass import DatabaseAttr, DatabaseClass

from Person import Person
from Entity import Entity
from Types import CodeType
from Commands import Commands

from SpineLib import Registry
from AllocationPeriod import AllocationAuthority
registry = Registry.get_registry()

#magic incantation; explanation _SHOULD_ be provided at a later date.
#Basically, list all classes defined or modified in this file.

__all__ = ['Project', 'Science', 'ProjectAllocationName', 'ProjectMember']

#Define supporting classes
table = 'science_code'
class Science(CodeType):
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

    
#We're defining a new class/entity - thus this is the way to do it.
table = 'project_info'
class Project(Entity):
    slots = Entity.slots + (
        DatabaseAttr('owner', table, Person, write=True, optional=False),
        DatabaseAttr('science', table, Science, write=True, optional=False),
        DatabaseAttr('title', table, str, write=True, optional=True),
        DatabaseAttr('description',table, str, write=True, optional=True)
    ) 
    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'project_id'
    }

    cerebrum_class = Factory.get('Project')
    entity_type = 'project'

registry.register_class(Project)


table = 'project_member'
class ProjectMember(DatabaseClass):
    primary = (
        DatabaseAttr('project', table, Project),
        DatabaseAttr('member', table, Person)
    )
    db_attr_aliases = {
        table:{
            'project':'project_id',
            'member':'member_id',
        }
    }
registry.register_class(ProjectMember)



table = 'project_allocation_name'
class ProjectAllocationName(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('project', table, Project),
        DatabaseAttr('allocation_authority', table, AllocationAuthority)
    )
    db_attr_aliases = {
        table:{
            'id':'project_allocation_name_id',
            'project':'project_id'
        }
    }
registry.register_class(ProjectAllocationName)



#define additional methods.

def create_project(self, owner, science, title, description):
    db = self.get_database()
    new_id = Project._create(db, owner.get_id(), science.get_id(), title, description)
    return Project(db, new_id)
create_project.signature = Project
create_project.signature_args = [Person, Science, str, str]
create_project.signature_write = True
Commands.register_method([create_project])

def add_member(self, member):

    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.add_member(member.get_id())

add_member.signature = None
add_member.signature_args = [Person]
add_member.signature_write = True

def remove_member(self, member):

    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.remove_member(member.get_id())

remove_member.signature = None
remove_member.signature_args = [Person]
remove_member.signature_write = True

def get_members(self):
    # XXX Want to use Hpc.py
    #obj = self._get_cerebrum_obj()
    #p = Cerebrum.modules.Hpc.Project(self.get_database())
    #p.find(obj.entity_id)
    #p.get_members()
    s = registry.ProjectMemberSearcher(self.get_database())
    s.set_project(self)
    return [i.get_member() for i in s.search()]

get_members.signature = [Person]

Project.register_methods([add_member, remove_member, get_members])


def add_allocation_name(self, name, authority):

    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.add_allocation_name(name, authority.get_id())

add_allocation_name.signature = None
add_allocation_name.signature_args = [str, AllocationAuthority]
add_allocation_name.signature_write = True

def remove_allocation_name(self, name):

    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.remove_allocation_name(name)

remove_allocation_name.signature = None
remove_allocation_name.signature_args = [str]
remove_allocation_name.signature_write = True


def remove_allocation_name(self, name):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    p.remove_allocation_name(name)

remove_allocation_name.signature = None
remove_allocation_name.signature_args = [str]
remove_allocation_name.signature_write = True

def get_allocation_names_str(self):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.Hpc.Project(self.get_database())
    p.find(obj.entity_id)
    return [i[0] for i in p.get_allocation_names()]
get_allocation_names_str.signature = [str]


def get_allocation_names(self):
    s = registry.ProjectAllocationNameSearcher(self.get_database())
    s.set_project(self)
    return s.search()
get_allocation_names.signature = [ProjectAllocationName]


Project.register_methods([add_allocation_name, remove_allocation_name,
                          get_allocation_names, get_allocation_names_str])

