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

"""Module for attaching notes to entities."""

from Cerebrum.Entity import Entity

__version__ = "1.0"

class EntityNote(Entity):
    "Mixin class, attach notes to any entity"

    def add_note(self, operator, subject, description=None):
        """Adds a note to this entity.

        @param operator: Entity ID of operator adding the note.
        @type operator: Integer

        @param subject: Note subject
        @type subject: String, < 70 characters

        @param description: Note description
        @type description: String, < 1024 characters

        @return Note ID
        @rtype Integer"""

        note_id = self.nextval("entity_note_seq")

        self.execute("""
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
        """Returns all notes associated with this entity.

        @return A list containing notes
        @rtype list of rows"""

        return self.query("""
        SELECT note_id, create_date, creator_id, subject, description
        FROM [:table schema=cerebrum name=entity_note] 
        WHERE entity_id=:e_id""",
            {
              'e_id': int(self.entity_id)
            })

    def list_all_notes(self, entity_type=None):
        """If entity_type is None, returns all notes associated with all 
        entities. If entity_type is set, it filters on this entity type.

        @param entity_type: Only return notes for entities of this type
        @type entity_type: EntityTypeCode or a list of EntityTypeCodes

        @return A list containing notes
        @rtype list of rows"""

        e_type = ""
        if entity_type is not None:
            e_type = """
            JOIN [:table schema=cerebrum name=entity_info] e
              ON e.entity_id = enote.entity_id AND
              e.entity_type """
            if isinstance(entity_type, list):
                e_type += "IN (%s)" % ", ".join(map(str,
                                                    map(int, entity_type)))
            else:
                e_type += "= %s" % int(entity_type)

        return self.query("""
        SELECT enote.note_id, enote.create_date, enote.creator_id, 
            enote.subject, enote.description
        FROM [:table schema=cerebrum name=entity_note] enote
        %s""" % e_type)
    
    def delete_note(self, note_id):
        """Deletes a note.

        @param note_id: Note ID to be removed
        @type note_id: Integer"""

        self.execute("""
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

    def delete(self):
        """Deletes all notes associated with this entity."""

        for note in self.get_notes():
            self.delete_note(note['note_id'])
        self.__super.delete()
