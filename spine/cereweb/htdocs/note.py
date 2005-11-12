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

import forgetHTML as html
from gettext import gettext as _
from lib.Main import Main
from lib.utils import transaction_decorator, commit
from lib.utils import redirect_object, queue_message
from lib.templates.NoteAddTemplate import NoteAddTemplate


def index(transaction, entity, subject="", description=""):
    """Shows the add-note-template."""
    entity = transaction.get_entity(int(entity))
    page = Main()
    noteadd = NoteAddTemplate()
    index = html.Division()
    index.append(html.Header(_("Add note for entity '%s':") % entity.get_id(), level=2))
    index.append(noteadd.addForm(entity))
    page.content = index.output
    return page
index = transaction_decorator(index)
index.exposed = True

def add(transaction, entity, subject="", description=""):
    """Adds a note to some entity."""
    entity = transaction.get_entity(int(entity))
    if not subject and not description:
        queue_message(_("Could not add blank note"), error=True)
        redirect_object(entity)
    else:
        entity.add_note(subject, description)
        commit(transaction, entity, msg=_("Added note '%s'") % subject)
add = transaction_decorator(add)
add.exposed = True

def delete(transaction, entity, id):
    """Removes a note."""
    entity = transaction.get_entity(int(entity))
    note = transaction.get_note(int(id))
    entity.remove_note(note)
    commit(transaction, entity, _("Note deleted"))
delete = transaction_decorator(delete)
delete.exposed = True

# arch-tag: a346491e-4e47-42c1-8646-391b6375b69f
