# -*- coding: iso-8859-1 -*-
# Copyright 2013 University of Oslo, Norway
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

"""
Module for attaching notes to entities.
"""

import cereconf
from Cerebrum.Entity import Entity

__version__ = "1.1"

class EntityNote(Entity):
    "Mixin class, attach notes to any entity"

    def add_note(self, operator, subject, description=None):
        """Adds a note to this entity.

        @param operator: Entity ID of operator adding the note.
        @type operator: Integer

        @param subject: Note subject
        @type subject: String, < 70 characters

        @param description: Note description
        @type description: String, < 1024 characters"""

        note_id = self.nextval("entity_note_seq")

        q = self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_note]
          (note_id, entity_id, creator_id, subject, description)
        VALUES (:n_id, :e_id, :c_id, :subject, :description)""",
            {'n_id': int(note_id),
             'e_id': int(self.entity_id),
             'c_id': int(operator),
             'subject': subject,
             'description': description,
            })

        self._db.log_change(self.entity_id, self.const.entity_note_add, None, 
                            change_params={
                                'note_id': int(note_id),
                            })

        return note_id
        
    def get_notes(self):
        """Returns all notes associated with this entity."""

        notes = self.query("""
        SELECT note_id, create_date, creator_id, subject, description
        FROM [:table schema=cerebrum name=entity_note] 
        WHERE entity_id=:e_id""",
            {
              'e_id': int(self.entity_id)
            })
        
        return notes

    def list_all_notes(self):
        """Returns all notes associated with all entities."""

        notes = self.query("""
        SELECT note_id, create_date, creator_id, subject, description
        FROM [:table schema=cerebrum name=entity_note]""")
        
        return notes
    
    def delete_note(self, note_id):
        """Deletes a note.

        @param note_id: Note ID to be removed
        @param note_id: Integer"""

        q = self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_note] 
        WHERE entity_id=:e_id AND note_id=:n_id""", 
            {
              'e_id': self.entity_id,
              'n_id': note_id
            })

        self._db.log_change(self.entity_id, self.const.entity_note_del, None, 
                            change_params={
                                'note_id': int(note_id),
                            })

        return q

    def delete(self):
        """Deletes all notes associated with this entity."""

        for note in self.get_notes():
            self.delete_note(note['note_id'])
        self.__super.delete()
