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

from gettext import gettext as _
from lib.data.NoteDAO import NoteDAO
from lib.forms import NoteCreateForm
from lib import utils

@utils.session_required_decorator
def add(entity_id, **kwargs):
    """Adds a note to some entity."""
    form = NoteCreateForm(entity_id, **kwargs)
    if form.is_correct():
        return make(**form.get_values())
    return form.respond()
add.exposed = True


@utils.session_required_decorator
def delete(entity_id, note_id):
    """Removes a note."""
    db = utils.get_database()
    dao = NoteDAO(db)
    dao.delete(entity_id, note_id)
    db.commit()

    utils.queue_message(_("Note successfully deleted."),
                        title="Change succeeded")
    utils.redirect_entity(entity_id)
delete.exposed = True

clean = lambda x: x and utils.web_to_spine(x.strip()) or None

def make(entity_id, subject, body):
    entity_id = int(entity_id)
    subject = clean(subject)
    body = clean(body)

    db = utils.get_database()
    dao = NoteDAO(db)
    dao.add(entity_id, subject, body)
    db.commit()
    
    utils.queue_message(_("Note successfully created."), title="Note created")
    utils.redirect_entity(entity_id)
    
# arch-tag: a346491e-4e47-42c1-8646-391b6375b69f
