# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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
from Cereweb.Main import Main
from Cereweb.utils import redirect_object, queue_message, transaction_decorator
from Cereweb.templates.NoteAddTemplate import NoteAddTemplate


@transaction_decorator
def index(req, transaction, entity, subject="", description=""):
    """Shows the add-note-template."""
    entity = transaction.get_entity(int(entity))
    page = Main(req)
    noteadd = NoteAddTemplate()
    index = html.Division()
    index.append(html.Header(_("Add note for entity '%s':") % entity.get_id(), level=2))
    index.append(noteadd.addForm(entity))
    page.content = index.output
    return page

@transaction_decorator
def add(req, transaction, entity, subject, description):
    """Adds a note to some entity."""
    entity = transaction.get_entity(int(entity))
    entity.add_note(subject, description)
    queue_message(req, _("Added note '%s'") % subject)
    redirect_object(req, entity, seeOther=True)

    transaction.commit()

@transaction_decorator
def delete(req, transaction, entity, id):
    """Removes a note."""
    entity = transaction.get_entity(int(entity))
    note = transaction.get_note(int(id))
    entity.remove_note(note)
    queue_message(req, _("Note deleted"))
    redirect_object(req, entity, seeOther=True)

# arch-tag: a346491e-4e47-42c1-8646-391b6375b69f
