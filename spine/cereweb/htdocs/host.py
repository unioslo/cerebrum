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
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.utils import rollback_url, session_required_decorator
from lib.utils import spine_to_web, web_to_spine, url_quote
from lib.utils import get_database
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
def edit(*args, **kwargs):
    """
    Creates a page with the form for editing a host.
    """
    form = HostEditForm(*args, **kwargs)
    if form.is_correct():
        return save(*args, **kwargs)
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(*args, **kwargs):
    """Creates a page with the form for creating a host."""
    form = HostCreateForm(*args, **kwargs)
    if form.is_correct():
        return make(*args, **kwargs)
    return form.respond()
create.exposed = True

def save(transaction, id, name, description="", submit=None):
    """Saves the information for the host."""
    host = transaction.get_host(int(id))
    if submit == 'Cancel':
        redirect_object(host)
    if name:
        name = web_to_spine(name.strip())
    host.set_name(name)
    if description:
        description = web_to_spine(description.strip())
    host.set_description(description)
    commit(transaction, host, msg=_("Host successfully updated."))
save = transaction_decorator(save)

def make(transaction, name, description=""):
    """Creates the host."""
    msg=''
    if not name:
        msg=_('Hostname is empty.')
    if not msg:
        if name:
            name = web_to_spine(name.strip())
        if description:
            description = web_to_spine(description.strip())
    if not msg:
        host = transaction.get_commands().create_host(name, description)
        commit(transaction, host, msg=_("Host successfully created."))
    else:
        rollback_url('/host/create', msg, err=True)
make = transaction_decorator(make)

def delete(transaction, id):
    """Delete the host from the server."""
    host = transaction.get_host(int(id))
    hostname = spine_to_web(host.get_name())
    msg = _("Host '%s' successfully deleted.") % hostname
    host.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def disks(transaction, host, add=None, delete=None, **checkboxes):
    if add:
        redirect('/disk/create?host=%s' % url_quote(host))
        
    elif delete:
        host = transaction.get_host(int(host))
        for arg, value in checkboxes.items():
            disk = transaction.get_disk(int(arg))
            disk.delete()
        
        if len(checkboxes) > 0:
            msg = _("Disk(s) successfully deleted.")
            commit(transaction, host, msg=msg)
        else:
            msg = _("No disk(s) selected for deletion")
            hostname = spine_to_web(host.get_name())
            queue_message(msg, error=True, link=object_link(host, text=hostname))
            redirect_object(host)
    else:
        raise "I don't know what you want me to do"
disks = transaction_decorator(disks)
disks.exposed = True

def promote_mailhost(transaction, id, type_id, promote=None):
    host_type = transaction.get_email_server_type(type_id)
    host = transaction.get_host(int(id))
    host.promote_email_server(host_type)
    msg = _('Host promoted to mailhost.')
    commit(transaction, host, msg=msg)
promote_mailhost = transaction_decorator(promote_mailhost)
promote_mailhost.exposed = True

def demote_mailhost(transaction, id):
    host = transaction.get_host(int(id))
    host.demote_email_server()
    msg = _('Host is no longer a mailhost.')
    commit(transaction, host, msg=msg)
demote_mailhost = transaction_decorator(demote_mailhost)
demote_mailhost.exposed = True

# arch-tag: 6d5f8060-3bf4-11da-96a8-c359dfc6e774
