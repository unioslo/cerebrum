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
from SpineLib.Builder import Method

from Person import Person
from Entity import Entity
from Types import CodeType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

#magic incantation; explanation _SHOULD_ be provided at a later date.
#Basically, list all classes defined or modified in this file.

__all__ = ['Project', 'Science']

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


#We're defining a new class - thus this is the way to do it.
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

#define additional methods.

def create(self, owner, science, title, description):
    db = self.get_database()
    new_id = Project._create(db, owner.get_id(), science.get_id(), title, description)
    return Project(db, new_id)
    
args = [('owner', Person), ('science', Science), ('title', str), ('description', str)]

#register ze newly defined methods
Commands.register_method(Method('create_project', Project, args=args, write=True), create)
