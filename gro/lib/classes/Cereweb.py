# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

from Builder import Method
from GroBuilder import GroBuilder
from DatabaseClass import DatabaseAttr, DatabaseClass
from Entity import Entity
from Date import Date

import Registry
registry = Registry.get_registry()

__all__ = ['CerewebOption','CerewebMotd']

option_table = "cereweb_option"

class CerewebOption(DatabaseClass):
    primary = [DatabaseAttr('id', option_table, int)]
    slots = [
        DatabaseAttr('entity', option_table, Entity),
        DatabaseAttr('key', option_table, str, write=True),
        DatabaseAttr('value', option_table, str, write=True)
    ]
    db_attr_aliases = {
        option_table: {'id': 'option_id', 'entity': 'entity_id'}
    }
    method_slots = [Method('delete', None, write=True)]

    def delete(self):
        self._delete()

registry.register_class(CerewebOption)

motd_table = "cereweb_motd"

class CerewebMotd(DatabaseClass):
    primary = [DatabaseAttr('id', motd_table, int)]
    slots = [
        DatabaseAttr('create_date', motd_table, Date),
        DatabaseAttr('creator', motd_table, Entity),
        DatabaseAttr('subject', motd_table, str),
        DatabaseAttr('message', motd_table, str)
    ]
    db_attr_aliases = {
        motd_table: {'id': 'motd_id'}
    }
    method_slots = [Method('delete', None, write=True)]

    def delete(self):
        self._delete()

registry.register_class(CerewebMotd)

class CerewebCommands(GroBuilder):
    method_slots = [
        Method('create_cereweb_motd', CerewebMotd, write=True,
                    args=[('subject', str), ('message', str)]),
        Method('create_cereweb_option', CerewebOption, write=True,
                    args=[('entity', Entity), ('key', str), ('value', str)])
    ]

    def __init__(self):
        GroBuilder.__init__(self, nocache=True)

    def create_cereweb_motd(self, subject, message):
        db = self.get_database()
        id = int(db.nextval('cereweb_seq'))
        creator = self.get_writelock_holder().get_client()
        CerewebMotd._create(db, id, creator=creator, subject=subject, message=message)
        return CerewebMotd(id, write_lock=self.get_writelock_holder())

    def create_cereweb_option(self, entity, key, value):
        db = self.get_database()
        id = int(db.nextval('cereweb_seq'))
        CerewebOption._create(db, id, entity, key, value)
        return CerewebOption(id, write_lock=self.get_writelock_holder())

registry.register_class(CerewebCommands)

# arch-tag: b89d1172-fbfc-4b63-959b-4689ce1ff025
