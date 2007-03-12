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

from account import _get_links
from gettext import gettext as _
from lib.Main import Main
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.utils import rollback_url
from lib.WorkList import remember_link
from lib.Searchers import HostSearcher
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.HostViewTemplate import HostViewTemplate
from lib.templates.HostEditTemplate import HostEditTemplate
from lib.templates.HostCreateTemplate import HostCreateTemplate

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Host")
    page.search_title = _('host(s)')
    page.set_focus("host/search")
    page.links = _get_links()

    page.search_fields = [("name", _("Name")),
                          ("description", _("Description"))
                        ]
    page.search_action = '/host/search'
    page.form_values = remembered
    return page.respond()

def search(transaction, **vargs):
    """Search for hosts and displays result and/or searchform."""
    args = ('name', 'description')
    searcher = HostSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the host given by id."""
    host = transaction.get_host(int(id))
    page = HostViewTemplate()
    page.title = _('Host %s') % host.get_name()
    page.set_focus('host/view')
    page.links = _get_links()
    server_type_searcher = transaction.get_email_server_type_searcher()
    type_names = [ (type.get_name(), type.get_name()) for type in server_type_searcher.search()]
    page.email_server_types = type_names
    page.entity = host
    page.entity_id = int(id)
    return page.respond()
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a host."""
    host = transaction.get_host(int(id))
    page = Main()
    # page.title = _("Edit ") + object_link(host)
    page.title = _("Host")
    page.set_focus("host/edit")
    page.links = _get_links()

    edit = HostEditTemplate()
    edit.title = _('Edit ') + object_link(host) + _(':')
    content = edit.editHost(host)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, name, description="", submit=None):
    """Saves the information for the host."""
    host = transaction.get_host(int(id))

    if submit == 'Cancel':
        redirect_object(host)
    
    host.set_name(name)
    host.set_description(description)
    commit(transaction, host, msg=_("Host successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def create(transaction, name="", description=""):
    """Creates a page with the form for creating a host."""
    page = Main()
    page.title = _("Host")
    page.set_focus("host/create")
    page.links = _get_links()

    # Store given create parameters in create-form
    values = {}
    values['name'] = name
    values['description'] = description

    create = HostCreateTemplate(searchList=[{'formvalues': values}])
    content = create.form()
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, name, description=""):
    """Creates the host."""
    msg=''
    if not name:
        msg=_('Hostname is empty.')
    if not msg:
        host = transaction.get_commands().create_host(name, description)
        commit(transaction, host, msg=_("Host successfully created."))
    else:
        rollback_url('/host/create', msg, err=True)
make = transaction_decorator(make)
make.exposed = True

def delete(transaction, id):
    """Delete the host from the server."""
    host = transaction.get_host(int(id))
    msg = _("Host '%s' successfully deleted.") % host.get_name()
    host.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def disks(transaction, host, add=None, delete=None, **checkboxes):
    if add:
        redirect('/disk/create?host=%s' % host)
        
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
            queue_message(msg, error=True, link=object_link(host))
            redirect_object(host)
    else:
        raise "I don't know what you want me to do"
disks = transaction_decorator(disks)
disks.exposed = True

def promote_mailhost(transaction, id, type):
    host_type = transaction.get_email_server_type(type)
    host = transaction.get_host(int(id))
    host.promote_email_server(host_type)
    transaction.commit()
    redirect('/host/view?id=%s' % id )
promote_mailhost = transaction_decorator(promote_mailhost)
promote_mailhost.exposed = True

def demote_mailhost(transaction, id):
    host = transaction.get_host(int(id))
    # host.demote_email_server()
    transaction.commit()
    redirect('/host/view?id=%s' % id )
demote_mailhost = transaction_decorator(demote_mailhost)
demote_mailhost.exposed = True

# arch-tag: 6d5f8060-3bf4-11da-96a8-c359dfc6e774
