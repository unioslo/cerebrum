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
from Cereweb.Main import Main
from Cereweb.utils import commit, commit_url, queue_message, object_link
from Cereweb.utils import url, transaction_decorator, redirect, redirect_object
from Cereweb.WorkList import remember_link
from Cereweb.templates.HostSearchTemplate import HostSearchTemplate
from Cereweb.templates.HostViewTemplate import HostViewTemplate
from Cereweb.templates.HostEditTemplate import HostEditTemplate
from Cereweb.templates.HostCreateTemplate import HostCreateTemplate

import Cereweb.config
max_hits = Cereweb.config.conf.getint('cereweb', 'max_hits')

def index(req):
    """Redirects to the page with search for hosts."""
    return search(req)

def search(req, transaction, name="", description="", offset=0):
    """Creates a page with a list of hosts matching the given criterias."""
    offset = int(offset)
    perform_search = False
    if name or description:
        perform_search = True
        req.session['host_ls'] = (name, description)
    elif 'host_ls' in req.session:
        name, description = req.session['host_ls']
        
    page = Main(req)
    page.title = _("Search for hosts(s)")
    page.setFocus("host/search")
    page.add_jscript("search.js")
    
    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['description'] = description
    form = HostSearchTemplate(searchList=[{'formvalues': values}])
    
    if perform_search:
        searcher = transaction.get_host_searcher()
        searcher.set_search_limit(max_hits + 1, offset)

        if name:
            searcher.set_name_like(name)

        if description:
            searcher.set_description_like(description)
            
        hosts = searcher.search()

        # Print results
        result = html.Division(_class="searchresult")
        hits = len(hosts)
        header = html.Header('Search results:', level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Name"), _("Description"), _("Actions"))
        for host in hosts[:max_hits]:
            edit = str(object_link(host, text="edit", method="edit", _class="actions"))
            remb = str(remember_link(host, _class="actions"))
            table.add(object_link(host), host.get_description(), edit+remb)
    
        if hosts:
            result.append(table)
        else:
            error = "Sorry, no host(s) found matching the given criteria!"
            result.append(html.Division(_(error), _class="searcherror"))

        result = html.Division(result)
        header = html.Header(_("Search for other host(s):"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        result.append(form.form())
        page.content = result.output
    else:
        page.content = form.form
    
    return page
search = transaction_decorator(search)

def view(req, transaction, id):
    """Creates a page with a view of the host given by id."""
    host = transaction.get_host(int(id))
    page = Main(req)
    page.title = _("Host %s" % host.get_name())
    page.setFocus("host/view", id)
    view = HostViewTemplate()
    content = view.viewHost(transaction, host)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    """Creates a page with the form for editing a host."""
    host = transaction.get_host(int(id))
    page = Main(req)
    page.title = _("Edit ") + object_link(host)
    page.setFocus("host/edit", id)

    edit = HostEditTemplate()
    content = edit.editHost(host)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def save(req, transaction, id, name, description="", submit=None):
    """Saves the information for the host."""
    host = transaction.get_host(int(id))

    if submit == 'Cancel':
        redirect_object(req, host, seeOther=True)
        return
    
    host.set_name(name)
    host.set_description(description)
    commit(transaction, req, host, msg=_("Host successfully updated."))
save = transaction_decorator(save)

def create(req, transaction, name="", description=""):
    """Creates a page with the form for creating a host."""
    page = Main(req)
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

def make(req, transaction, name, description=""):
    """Creates the host."""
    host = transaction.get_commands().create_host(name, description)
    commit(transaction, req, host, msg=_("Host successfully created."))
make = transaction_decorator(make)

def delete(req, transaction, id):
    """Delete the host from the server."""
    host = transaction.get_host(int(id))
    msg = _("Host '%s' successfully deleted.") % host.get_name()
    host.delete()
    commit_url(transaction, req, url("host/index"), msg=msg)
delete = transaction_decorator(delete)

def disks(req, transaction, host, add=None, delete=None, **checkboxes):
    if add:
        redirect(req, url('disk/create?host=%s' % host))
        
    elif delete:
        host = transaction.get_host(int(host))
        for arg, value in checkboxes.items():
            disk = transaction.get_disk(int(arg))
            disk.delete()
        
        if len(checkboxes) > 0:
            msg = _("Disk(s) successfully deleted.")
            commit(transaction, req, host, msg=msg)
        else:
            msg = _("No disk(s) selected for deletion")
            queue_message(req, msg, error=True, link=object_link(host))
            redirect_object(req, host, seeOther=True)
    else:
        raise "I don't know what you want me to do"
disks = transaction_decorator(disks)

# arch-tag: 6d5f8060-3bf4-11da-96a8-c359dfc6e774
