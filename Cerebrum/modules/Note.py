# -*- coding: utf-8 -*-
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
from Cerebrum.Utils import argument_to_sql

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

        self._db.log_change(self.entity_id, self.clconst.entity_note_add, None,
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
        WHERE entity_id=:e_id""", {'e_id': int(self.entity_id)})

    def list_all_notes(self, entity_type=None):
        """If entity_type is None, returns all notes associated with all
        entities. If entity_type is set, it filters on this entity type.

        @param entity_type: Only return notes for entities of this type
        @type entity_type: EntityTypeCode or a list of EntityTypeCodes

        @return A list containing notes
        @rtype list of rows"""

        tables = ["[:table schema=cerebrum name=entity_note] enote"]
        where = []
        binds = {}

        if entity_type is not None:
            tables.append("""[:table schema=cerebrum name=entity_info] e""")
            where.append("enote.entity_id = e.entity_id")
            where.append(
                argument_to_sql(entity_type, "e.entity_type", binds, int))

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        query_str = """SELECT enote.note_id, enote.create_date,
            enote.creator_id, enote.subject, enote.description
            FROM %s %s""" % (", ".join(tables), where_str)

        return self.query(query_str, binds, fetchall=True)

    def delete_note(self, note_id):
        """Deletes a note.

        @param note_id: Note ID to be removed
        @type note_id: Integer"""
        binds = {'e_id': self.entity_id,
                 'n_id': note_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=entity_note]
            WHERE entity_id=:e_id AND note_id=:n_id
          )
        """
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=entity_note]
          WHERE entity_id=:e_id AND note_id=:n_id
        """
        self.execute(delete_stmt, binds)
        self._db.log_change(self.entity_id,
                            self.clconst.entity_note_del,
                            None,
                            change_params={'note_id': int(note_id)})

    def delete(self):
        """Deletes all notes associated with this entity."""

        for note in self.get_notes():
            self.delete_note(note['note_id'])
        self.__super.delete()
