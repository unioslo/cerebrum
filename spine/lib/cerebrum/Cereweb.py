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
from SpineLib.SpineClass import SpineClass
from SpineLib.DatabaseClass import DatabaseAttr, DatabaseClass
from SpineLib.Date import Date

from Entity import Entity
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['CerewebOption','CerewebMotd']

option_table = "cereweb_option"

class CerewebOption(DatabaseClass):
    """Key:Value Option for entities.

    Cereweb-specific options where both key and value is string.
    """
    
    primary = (
        DatabaseAttr('id', option_table, int),
    )
    slots = (
        DatabaseAttr('entity', option_table, Entity),
        DatabaseAttr('section', option_table, str),
        DatabaseAttr('key', option_table, str),
        DatabaseAttr('value', option_table, str, write=True)
    )
    method_slots = (
        Method('delete', None, write=True),
    )
    db_attr_aliases = {
        option_table: {'id': 'option_id', 'entity': 'entity_id'}
    }

    def delete(self):
        self._delete_from_db()

registry.register_class(CerewebOption)

motd_table = "cereweb_motd"

class CerewebMotd(DatabaseClass):
    """Message of the day.

    Cereweb-specific message of the day. No writeable attributes, to
    avoid the need to have change-dates and info about who changed it.
    """
    
    primary = (
        DatabaseAttr('id', motd_table, int),
    )
    slots = (
        DatabaseAttr('create_date', motd_table, Date),
        DatabaseAttr('creator', motd_table, Entity),
        DatabaseAttr('subject', motd_table, str),
        DatabaseAttr('message', motd_table, str)
    )
    method_slots = (
        Method('delete', None, write=True),
    )
    db_attr_aliases = {
        motd_table: {'id': 'motd_id'}
    }

    def delete(self):
        self._delete_from_db()

registry.register_class(CerewebMotd)

def create_motd(self, subject, message):
    """Create a new motd.
    
    Create a new Message-of-the-day.
    """
    db = self.get_database()
    id = int(db.nextval('cereweb_seq'))
    CerewebMotd._create(db, id, creator=db.change_by, subject=subject, message=message)
    return CerewebMotd(db, id)

Commands.register_method(Method('create_cereweb_motd', CerewebMotd, write=True,
            args=[('subject', str), ('message', str)]), create_motd)

def create_option(self, entity, section, key, value):
    """Create a new option.

    Create a new key:value option.
    """
    db = self.get_database()
    id = int(db.nextval('cereweb_seq'))
    CerewebOption._create(db, id, entity, section, key, value)
    return CerewebOption(db, id)

Commands.register_method(Method('create_cereweb_option', CerewebOption,
                         write=True, args=[('entity', Entity), ('section', str),
                         ('key', str), ('value', str)]), create_option)

# arch-tag: f21ea724-a469-4ef8-87bf-1eae1493717c
