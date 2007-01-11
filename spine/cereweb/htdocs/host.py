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
from lib.utils import rollback_url
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.HostSearchTemplate import HostSearchTemplate
from lib.templates.HostViewTemplate import HostViewTemplate
from lib.templates.HostEditTemplate import HostEditTemplate
from lib.templates.HostCreateTemplate import HostCreateTemplate


def search(transaction, **vargs):
    """Search for hosts and displays result and/or searchform."""
    page = Main()
    page.title = _("Search for hosts(s)")
    page.setFocus("host/search")
    page.add_jscript("search.js")
    
    handler = SearchHandler('host', HostSearchTemplate().form)
    handler.args = ('name', 'description')
    handler.headers = (
        ('Name', 'name'), ('Description', 'description'), ('Actions', '')
    )
    
    def search_method(values, offset, orderby, orderby_dir):
        name, description = values
        
        searcher = transaction.get_host_searcher()
        setup_searcher([searcher], orderby, orderby_dir, offset)
        
        if name:
            searcher.set_name_like(name)
        if description:
            searcher.set_description_like(description)
            
        return searcher.search()

    def row(elm):
        edit = object_link(elm, text='edit', method='edit', _class='actions')
        remb = remember_link(elm, _class='actions')
        return object_link(elm), elm.get_description(), str(edit)+str(remb)
    
    hosts = handler.search(search_method, **vargs)
    result = handler.get_result(hosts, row)
    page.content = lambda: result
    
    return page
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the host given by id."""
    host = transaction.get_host(int(id))
    page = Main()
    page.title = _('Host %s') % host.get_name()
    page.setFocus('host/view', id)
    content = HostViewTemplate().view(transaction, host)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a host."""
    host = transaction.get_host(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(host)
    page.setFocus("host/edit", id)

    edit = HostEditTemplate()
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
    page.title = _("Create a new host")
    page.setFocus("host/create")

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

# arch-tag: 6d5f8060-3bf4-11da-96a8-c359dfc6e774
