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
from lib.Main import Main
from lib.utils import commit, commit_url, entity_link, object_link
from lib.utils import transaction_decorator, redirect_object, html_quote
from lib.utils import spine_to_web, web_to_spine, session_required_decorator
from lib.utils import get_database
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
def edit(*args, **kwargs):
    """
    Creates a page with the form for editing a disk.
    """
    form = DiskEditForm(*args, **kwargs)
    if form.is_correct():
        return save(*args, **kwargs)
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(*args, **kwargs):
    """Creates a page with the form for creating a disk."""
    form = DiskCreateForm(*args, **kwargs)
    if form.is_correct():
        return make(*args, **kwargs)
    return form.respond()
create.exposed = True

def save(transaction, id, path="", description="", submit=None):
    """Saves the information for the disk."""
    disk = transaction.get_disk(int(id))

    if submit == 'Cancel':
        redirect_object(disk)
        return
    if path:
        path = web_to_spine(path.strip())
    disk.set_path(path)
    if description:
        description = web_to_spine(description.strip())
    disk.set_description(description)
    
    commit(transaction, disk, msg=_("Disk successfully updated."))
save = transaction_decorator(save)

def make(transaction, host, path="", description=""):
    """Creates the host."""
    host = transaction.get_host(int(host))
    thePath = web_to_spine(path.strip())
    desc = web_to_spine(description.strip())
    disk = transaction.get_commands().create_disk(host, thePath, desc)
    commit(transaction, disk, msg=_("Disk successfully created."))
make = transaction_decorator(make)

def delete(transaction, id):
    """Delete the disk from the server."""
    disk = transaction.get_disk(int(id))
    msg = _("Disk '%s' successfully deleted.") % spine_to_web(disk.get_path())
    disk.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

