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
from Cereweb.utils import redirect_object, queue_message
from Cereweb.templates.NoteAddTemplate import NoteAddTemplate


def index(req, entity, subject="", description=""):
    """Shows the add-note-template."""
    server = req.session.get("active")
    entity = server.get_entity(int(entity))
    page = Main(req)
    noteadd = NoteAddTemplate()
    index = html.Division()
    index.append(html.Header(_("Add note for entity '%s':") % entity.get_entity_id(), level=2))
    index.append(noteadd.addForm(entity))
    page.content = index.output
    return page

def add(req, entity, subject, description):
    """Adds a note to some entity."""
    server = req.session.get("active")
    entity = server.get_entity(int(entity))
    entity.add_note(subject, description)
    queue_message(req, _("Added note '%s'") % subject)
    return redirect_object(req, entity, seeOther=True)

def delete(req, entity, id):
    """Removes a note."""
    server = req.session.get("active")
    entity = server.get_entity(int(entity))
    entity.remove_note(int(id))
    queue_message(req, _("Note deleted"))
    return redirect_object(req, entity, seeOther=True)

# arch-tag: a346491e-4e47-42c1-8646-391b6375b69f
