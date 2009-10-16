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
from lib.utils import url_quote, entity_link
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DiskDAO import DiskDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.HostDAO import HostDAO
from lib.data.NoteDAO import NoteDAO
from lib.data.TraitDAO import TraitDAO
from lib.HostSearcher import HostSearcher
from lib.templates.HostViewTemplate import HostViewTemplate
from lib.forms import HostCreateForm, HostEditForm

@session_required_decorator
def search(**vargs):
    """
    Search for hosts and displays result and/or searchform.

    Will always perform a search with no arguments, returning all rows since
    the HostSearcher has no required fields.
    """
    searcher = HostSearcher(**vargs)
    return searcher.respond()
search.exposed = True
index = search

@session_required_decorator
def view(id):
    """Creates a page with a view of the host given by id."""
    db = get_database()
    dao = HostDAO(db)
    host = dao.get(id)
    host.disks = DiskDAO(db).search(host_id=id)
    host.traits = TraitDAO(db).get(id)
    host.notes = NoteDAO(db).get(id)
    host.history = HistoryDAO(db).get_entity_history_tail(id)

    page = HostViewTemplate()
    page.host = host
    page.email_server_types = ConstantsDAO(db).get_email_server_types()

    return page.respond()
view.exposed = True

@session_required_decorator
def edit(id, *args, **kwargs):
    """
    Creates a page with the form for editing a host.
    """
    form = HostEditForm(id, *args, **kwargs)
    if form.is_correct():
        return save(**form.get_values())
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(*args, **kwargs):
    """Creates a page with the form for creating a host."""
    form = HostCreateForm(*args, **kwargs)
    if form.is_correct():
        return make(**form.get_values())
    return form.respond()
create.exposed = True

@session_required_decorator
def save(id, name, description):
    """Saves the information for the host."""
    db = get_database()
    dao = HostDAO(db)
    host = dao.get(id)
    host.name = web_to_spine(name).strip()
    host.description = web_to_spine(description).strip()
    dao.save(host)
    db.commit()

    queue_message(_("Host successfully updated."), title=_("Change succeeded"))
    redirect_entity(host)

@session_required_decorator
def make(name, description):
    """Creates the host."""
    db = get_database()
    dao = HostDAO(db)
    host = dao.create(
        web_to_spine(name).strip(),
        web_to_spine(description).strip())
    db.commit()

    queue_message(_("Host successfully created."), title=_("Change succeeded"))
    redirect_entity(host)

@session_required_decorator
def delete(id):
    """Delete the host from the server."""
    db = get_database()
    dao = HostDAO(db)
    host = dao.get(id)
    dao.delete(id)
    db.commit()

    msg = _("Host '%s' successfully deleted.") % spine_to_web(host.name)
    redirect('/host/')
delete.exposed = True

@session_required_decorator
def disks(host_id, delete=None, **checkboxes):
    if delete:
        return delete_disks(host_id, **checkboxes)
    else:
        queue_message(_("Unknown operation."), title=_("Change failed"), error=True)
        redirect_entity(host_id)
disks.exposed = True

def delete_disks(host_id, **checkboxes):
    db = get_database()
    dao = DiskDAO(db)

    for disk_id, value in checkboxes.items():
        dao.delete(disk_id)

    if len(checkboxes) > 0:
        queue_message(_("Disk(s) successfully deleted."), title=_("Change succeeded"))
        db.commit()
    else:
        queue_message(_("No disk(s) selected for deletion"), title=_("Change failed"), error=True)
    redirect_entity(host_id)

@session_required_decorator
def promote_mailhost(host_id, type_id, promote=None):
    db = get_database()
    dao = HostDAO(db)
    dao.promote_mailhost(host_id, type_id)
    db.commit()

    queue_message(_('Host promoted to mailhost.'), title=_("Change succeeded"))
    redirect_entity(host_id)
promote_mailhost.exposed = True

@session_required_decorator
def demote_mailhost(host_id):
    db = get_database()
    dao = HostDAO(db)
    dao.demote_mailhost(host_id)
    db.commit()

    queue_message(_('Host is no longer a mailhost.'), title=_("Change succeeded"))
    redirect_entity(host_id)
demote_mailhost.exposed = True
