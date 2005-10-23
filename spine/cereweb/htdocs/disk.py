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
from Cereweb.utils import commit, commit_url, url, object_link
from Cereweb.utils import transaction_decorator, redirect_object
from Cereweb.WorkList import remember_link
from Cereweb.templates.DiskSearchTemplate import DiskSearchTemplate
from Cereweb.templates.DiskViewTemplate import DiskViewTemplate
from Cereweb.templates.DiskEditTemplate import DiskEditTemplate
from Cereweb.templates.DiskCreateTemplate import DiskCreateTemplate

import Cereweb.config
max_hits = Cereweb.config.conf.getint('cereweb', 'max_hits')

def index(req):
    return search(req)

def search(req, transaction, path="", description=""):
    """Creates a page with a list of disks matching the given criterias."""
    perform_search = False
    if path or description:
        perform_search = True
        req.session['disk_ls'] = (path, description)
    elif 'disk_ls' in req.session:
        path, description = req.session['disk_ls']
    
    page = Main(req)
    page.title = _("Search for disk(s)")
    page.setFocus("disk/search")
    
    # Store given search parameters in search form
    values = {}
    values['path'] = path
    values['description'] = description
    form = DiskSearchTemplate(searchList=[{'formvalues': values}])
    
    if perform_search:
        disksearcher = transaction.get_disk_searcher()

        if path:
            disksearcher.set_path_like(path)

        if description:
            disksearcher.set_description_like(description)
            
        disks = disksearcher.search()

        # Print results
        result = html.Division(_class="searchresult")
        hits = len(disks)
        header = html.Header('%s hits, showing 0-%s' % (hits, min(max_hits, hits)), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Path"), _("Host"), _("Description"), _("Actions"))
        for disk in disks[:max_hits]:
            path = object_link(disk, text=disk.get_path())
            edit = str(object_link(disk, text="edit", method="edit", _class="actions"))
            remb = str(remember_link(disk, _class="actions"))
            table.add(path, object_link(disk.get_host()), disk.get_description(), edit+remb)
    
        if disks:
            result.append(table)
        else:
            error = "Sorry, no disk(s) found matching the given criteria!"
            result.append(html.Division(_(error), _class="searcherror"))

        result = html.Division(result)
        header = html.Header(_("Search for other disk(s):"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        result.append(form.form())
        page.content = result.output
    else:
        page.content = form.form
    
    return page
search = transaction_decorator(search)

def view(req, transaction, id):
    """Creates a page with a view of the disk given by id."""
    disk = transaction.get_disk(int(id))
    page = Main(req)
    page.title = _("Disk %s" % disk.get_path())
    page.setFocus("disk/view", id)
    view = DiskViewTemplate()
    content = view.viewDisk(transaction, disk)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    """Creates a page with the form for editing a disk."""
    disk = transaction.get_disk(int(id))
    page = Main(req)
    page.title = _("Edit ") + object_link(disk)
    page.setFocus("disk/edit", id)

    edit = DiskEditTemplate()
    content = edit.editDisk(disk)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def save(req, transaction, id, path="", description="", submit=None):
    """Saves the information for the disk."""
    disk = transaction.get_disk(int(id))

    if submit == 'Cancel':
        redirect_object(req, disk, seeOther=True)
        return
    
    disk.set_path(path)
    disk.set_description(description)
    
    commit(transaction, req, disk, msg=_("Disk successfully updated."))
save = transaction_decorator(save)

def create(req, transaction, host=""):
    """Creates a page with the form for creating a disk."""
    page = Main(req)
    page.title = _("Create a new disk")
    page.setFocus("disk/create")

    hosts = [(i.get_id(), i.get_name()) for i in
                    transaction.get_host_searcher().search()]

    create = DiskCreateTemplate()
    if host:
        create.formvalues = {'host': int(host)}
    content = create.form(hosts)
    page.content = lambda: content
    return page
create = transaction_decorator(create)

def make(req, transaction, host, path="", description=""):
    """Creates the host."""
    host = transaction.get_host(int(host))
    disk = transaction.get_commands().create_disk(host, path, description)
    commit(transaction, req, disk, msg=_("Disk successfully created."))
make = transaction_decorator(make)

def delete(req, transaction, id):
    """Delete the disk from the server."""
    disk = transaction.get_disk(int(id))
    msg = _("Disk '%s' successfully deleted.") % disk.get_path()
    disk.delete()
    commit_url(transaction, req, url("disk/index"), msg=msg)
delete = transaction_decorator(delete)

# arch-tag: 6cf3413e-3bf4-11da-9d43-c8c980cc74d7
