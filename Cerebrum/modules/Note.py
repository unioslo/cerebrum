# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

class EntityNote(Entity):
    "Mixin class, attach notes to any entity"
    def add_note(self, creator, subject, description=None):
        note_id = self.nextval("note_seq")
        a = self.execute("""
        INSERT INTO [:table schema=cerebrum name=note]
          (note_id, entity_id, creator_id, subject, description)
        VALUES (:n_id, :e_id, :c_id, :subject, :description)""",
                     {'n_id': int(note_id),
                      'e_id': int(self.entity_id),
                      'c_id': int(creator),
                      'subject': str(subject),
                      'description': str(description),
                     })

       # Is this the correct way to log changes?
        self._db.log_change(self.entity_id, self.const.note_add,
                            None,
                            change_params={
                            'note_id': int(note_id),
                            'subject': str(subject) })
    def get_notes(self):
        a = self.query("""
        SELECT note_id, create_date, creator_id, subject, description
        FROM [:table schema=cerebrum name=note] 
        WHERE entity_id=:e_id""", {'e_id': int(self.entity_id)})
        return a
    
    def delete_note(self, deleter, note_id):    
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=note] 
        WHERE entity_id=:e_id AND note_id=:n_id""", 
        {'e_id': self.entity_id, 'n_id': note_id})
        self._db.log_change(self.entity_id, self.const.note_del,
                            None, change_params={'note_id': int(note_id)})

