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

from SpineLib.Builder import Attribute, Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Date import Date
from Entity import Entity

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Note']

class Note(DatabaseClass):
    primary = [
        DatabaseAttr('id', 'note', int)
    ]
    slots = [
        DatabaseAttr('create_date', 'note', Date),
        DatabaseAttr('creator', 'note', Entity),
        DatabaseAttr('entity', 'note', Entity),
        DatabaseAttr('subject', 'note', str),
        DatabaseAttr('description', 'note', str)
    ]
    method_slots = [
        Method('delete', None, write=True)
    ]
    
    db_attr_aliases = {
        'note': {
            'id': 'note_id',
            'creator': 'creator_id',
            'entity': 'entity_id'
        }
    }

    def delete(self):
        self._delete()
        self.invalidate()

registry.register_class(Note)

def add_note(self, subject, description):
    db = self.get_database()
    import Cerebrum.modules.Note
    e = Cerebrum.modules.Note.EntityNote(db)
    e.entity_id = self.get_id()

    e.add_note(db.change_by, subject, description)

Entity.register_method(Method('add_note', None, args=[('subject', str), ('description', str)], write=True), add_note)

def remove_note(self, note):
    note.delete()

Entity.register_method(Method('remove_note', None, args=[('note', Note)], write=True), remove_note)

def get_notes(self):
    s = registry.NoteSearcher(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_notes', [Note]), get_notes)

# arch-tag: d6c21535-3c25-41b7-b8f3-5cdb69d7f90d
