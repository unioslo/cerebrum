# -*- coding: utf-8 -*-
#
# Copyright 2016-2026 University of Oslo, Norway
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
Entity mixins for the note module.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.Entity import Entity
from .note_db import sql_add_note, sql_delete_notes, sql_search_notes


class EntityNoteCleanupMixin(Entity):
    """
    Mixin to provide note cleanup.

    This is the base mixin for notes, and should be added to
    ``cereconf.CLASS_ENTITY`` if the entity note database schema is installed.

    Without this, ``Entity.delete()`` calls may run into constraints whenever
    an Entity with a note is deleted.
    """

    def delete(self):
        """
        Delete this entity and all notes associated with this entity.

        .. note::
            This entity may be a *note creator* for notes associated with
            *other* entities. These notes will not be deleted - and constraints
            prevent us from deleting this entity.
        """
        sql_delete_notes(db=self._db, entity_id=int(self.entity_id))
        super(EntityNoteCleanupMixin, self).delete()


class EntityNoteMixin(EntityNoteCleanupMixin):
    """
    Mixin class with convenience methods for adding and removing notes.

    Entities with this mixin have the note feature enabled.
    """

    def add_note(self, operator, subject, description=None):
        """
        Adds a note to this entity.

        :param int operator: account id of operator adding the note.
        :param str subject: note subject (header), < 70 chars
        :param str description: note description (body)

        :returns int: the note id of the new note
        """
        note = sql_add_note(
            db=self._db,
            entity_id=self.entity_id,
            creator_id=operator,
            subject=subject,
            description=description,
        )
        return note['note_id']

    def get_notes(self):
        """
        Returns all notes associated with this entity.

        :returns: A sequence of note rows
        """
        return sql_search_notes(
            db=self._db, fetchall=True, entity_id=int(self.entity_id)
        )

    def delete_note(self, note_id):
        """
        Deletes a note.

        .. note::
           The note-id must be associated with this entity.  If it's associated
           with another entity, nothing happens.

        :param int note_id: id of note to remove
        """
        sql_delete_notes(
            db=self._db, entity_id=int(self.entity_id), note_id=int(note_id)
        )
