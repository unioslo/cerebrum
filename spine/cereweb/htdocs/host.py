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

import sets
import forgetHTML as html
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator, object_link
from Cereweb.WorkList import remember_link
from Cereweb.templates.HostSearchTemplate import HostSearchTemplate
from Cereweb.templates.HostViewTemplate import HostViewTemplate
from Cereweb.templates.HostEditTemplate import HostEditTemplate
from Cereweb.templates.HostCreateTemplate import HostCreateTemplate

import Cereweb.config
max_hits = Cereweb.config.conf.getint('cereweb', 'max_hits')

def index(req):
    """Creates a page with the search for hosts."""
    page = Main(req)
    page.title = _("Search for host(s)")
    page.setFocus("host/search")
    hostsearch = HostSearchTemplate()
    page.content = hostsearch.form
    return page

def list(req):
    """Creates a page wich content is the last host search performed."""
    return search(req, *req.session.get('host_lastsearch', ()))

def search(req, name="", description="", transaction=None):
    """Creates a page with a list of hosts matching the given criterias."""
    req.session['host_lastsearch'] = (name, description)
    page = Main(req)
    page.title = _("Search for hosts(s)")
    page.setFocus("host/list")
    
    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['description'] = description
    form = HostSearchTemplate(searchList=[{'formvalues': values}])
    
    if name or description:
        searcher = transaction.get_host_searcher()

        if name:
            searcher.set_name_like(name)

        if description:
            searcher.set_description_like(description)
            
        hosts = searcher.search()

        # Print results
        result = html.Division(_class="searchresult")
        hits = len(hosts)
        header = html.Header('%s hits, showing 0-%s' % (hits, min(max_hits, hits)), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Name"), _("Description"), _("Actions"))
        for host in hosts[:max_hits]:
            view = str(object_link(host, text="view", _class="actions"))
            edit = str(object_link(host, text="edit", method="edit", _class="actions"))
            remb = str(remember_link(host, _class="actions"))
            table.add(object_link(host), host.get_description(), view+edit+remb)
    
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
    page.setFocus("host/view", str(host.get_id()))
    view = HostViewTemplate()
    content = view.viewHost(transaction, host)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    """Creates a page with the form for editing a host."""
    host = transaction.get_host(int(id))
    page = Main(req)
    page.title = _("Edit %s" % host.get_name())
    page.setFocus("host/edit", str(host.get_id()))

    edit = HostEditTemplate()
    content = edit.editHost(host)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def save(req, transaction, id, name, description=""):
    """Saves the information for the host."""
    host = transaction.get_host(int(id))
    host.set_name(name)
    host.set_description(description)
    
    redirect_object(req, host, seeOther=True)
    transaction.commit()
    queue_message(req, _("Host successfully updated."))
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
    redirect_object(req, host, seeOther=True)
    transaction.commit()
    queue_message(req, _("Host successfully created."))
make = transaction_decorator(make)

def delete(req, transaction, id):
    """Delete the host from the server."""
    host = transaction.get_host(int(id))
    host.delete()

    redirect(req, url("host"), seeOther=True)
    transaction.commit()
    queue_message(req, "Host successfully deleted.")
delete = transaction_decorator(delete)

# arch-tag: 6d5f8060-3bf4-11da-96a8-c359dfc6e774
