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


from Builder import Attribute, Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Date import Date
from Entity import Entity

import Registry
registry = Registry.get_registry()

__all__ = ['Note']

class Note(DatabaseClass):
    cls_name = 'Note'
    primary = [
        DatabaseAttr('id', 'note', int, dbattr_name='note_id')
    ]
    slots = [
        DatabaseAttr('create_date', 'note', str),
        DatabaseAttr('creator', 'note', Entity, dbattr_name='creator_id'),
        DatabaseAttr('entity', 'note', Entity, dbattr_name='entity_id'),
        DatabaseAttr('subject', 'note', str),
        DatabaseAttr('description', 'note', str)
    ]

registry.register_class(Note)

def add_note(self, subject, description):
    db = self.get_database()
    import Cerebrum.modules.Note
    e = Cerebrum.modules.Note.EntityNote(db)
    e.entity_id = self.get_id()

    e.add_note(db.change_by, subject, description)

Entity.register_method(Method('add_note', None, args=[('subject', str), ('description', str)], write=True), add_note)

def get_notes(self):
    s = registry.NoteSearch()
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_notes', Note, sequence=True), get_notes)

# arch-tag: 051b4ae4-d46d-43b6-b339-fb857279db1f
