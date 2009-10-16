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

import cherrypy

from gettext import gettext as _
from lib.utils import redirect_entity, redirect
from lib.utils import spine_to_web, web_to_spine
from lib.utils import session_required_decorator
from lib.utils import get_database, queue_message
from lib.data.DiskDAO import DiskDAO
from lib.data.TraitDAO import TraitDAO
from lib.data.NoteDAO import NoteDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.forms import DiskCreateForm, DiskEditForm
from lib.DiskSearcher import DiskSearcher
from lib.templates.DiskViewTemplate import DiskViewTemplate

@session_required_decorator
def search(**vargs):
    """
    Search after disks and displays result and/or searchform.

    Will always perform a search with no arguments, returning all rows since
    the DiskSearcher has no required fields.
    """
    searcher = DiskSearcher(**vargs)
    return searcher.respond()
search.exposed = True
index = search

@session_required_decorator
def view(id):
    """Creates a page with a view of the disk given by id."""
    db = get_database()
    dao = DiskDAO(db)
    disk = dao.get(id)
    disk.traits = TraitDAO(db).get(id)
    disk.notes = NoteDAO(db).get(id)
    disk.history = HistoryDAO(db).get_entity_history_tail(id)

    page = DiskViewTemplate()
    page.disk = disk

    return page.respond()
view.exposed = True

@session_required_decorator
def edit(id, **kwargs):
    """
    Creates a page with the form for editing a disk.
    """
    form = DiskEditForm(id, **kwargs)
    if form.is_correct():
        return save(**form.get_values())
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(host_id=None, **kwargs):
    """Creates a page with the form for creating a disk."""
    form = DiskCreateForm(host_id, **kwargs)
    if form.is_correct():
        return make(**form.get_values())
    return form.respond()
create.exposed = True

def save(id, path, description):
    """Saves the information for the disk."""
    db = get_database()
    dao = DiskDAO(db)
    disk = dao.get(id)
    disk.path = web_to_spine(path).strip()
    disk.description = web_to_spine(description).strip()
    dao.save(disk)
    db.commit()

    queue_message(_("Disk successfully updated."), title=_("Change succeeded"))
    redirect_entity(disk)

def make(host_id, path, description):
    """Creates the disk."""
    db = get_database()
    dao = DiskDAO(db)
    disk = dao.create(
        int(host_id),
        web_to_spine(path).strip(),
        web_to_spine(description).strip())
    db.commit()

    queue_message(_("Disk successfully created."), title=_("Change succeeded"))
    redirect_entity(disk)

@session_required_decorator
def delete(id):
    """Delete the disk from the server."""
    db = get_database()
    dao = DiskDAO(db)
    disk = dao.get(id)
    dao.delete(id)
    db.commit()

    msg = _("Disk '%s' successfully deleted.") % spine_to_web(disk.path)
    redirect('/disk/')
delete.exposed = True

