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

from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import commit, commit_url, url, object_link
from Cereweb.utils import transaction_decorator, redirect_object
from Cereweb.WorkList import remember_link
from Cereweb.Search import get_arg_values, get_form_values, setup_searcher
from Cereweb.templates.SearchResultTemplate import SearchResultTemplate
from Cereweb.templates.DiskSearchTemplate import DiskSearchTemplate
from Cereweb.templates.DiskViewTemplate import DiskViewTemplate
from Cereweb.templates.DiskEditTemplate import DiskEditTemplate
from Cereweb.templates.DiskCreateTemplate import DiskCreateTemplate


def index(req):
    return search(req)

def search(req, transaction, offset=0, **vargs):
    """Search after disks and displays result and/or searchform."""
    page = Main(req)
    page.title = _("Search for disk(s)")
    page.setFocus("disk/search")
    page.add_jscript("search.js")
   
    searchform = DiskSearchTemplate()
    arguments = ['path', 'description', 'orderby', 'orderby_dir']
    values = get_arg_values(arguments, vargs)
    perform_search = len([i for i in values if i != ""])

    if perform_search:
        req.session['disk_ls'] = values
        path, description, orderby, orderby_dir = values

        disksearcher = transaction.get_disk_searcher()
        setup_searcher([disksearcher], orderby, orderby_dir, offset)

        if path:
            disksearcher.set_path_like(path)

        if description:
            disksearcher.set_description_like(description)
            
        disks = disksearcher.search()

        result = []
        display_hits = req.session['options'].getint('search', 'display hits')
        for disk in disks[:display_hits]:
            path = object_link(disk, text=disk.get_path())
            host = object_link(disk.get_host())
            desc = disk.get_description()
            edit = object_link(disk, text='edit', method='edit', _class='actions')
            remb = remember_link(disk, _class='actions')
            result.append((path, host, desc, str(edit) + str(remb)))

        headers = [('Path', 'path'), ('Host', ''), 
                   ('Description', 'description'), ('Actions', '')]

        template = SearchResultTemplate()
        table = template.view(result, headers, arguments, values,
            len(disks), display_hits, offset, searchform, 'disk/search')

        page.content = lambda: table
    else:
        rmb_last = req.session['options'].getboolean('search', 'remember last')
        if 'disk_ls' in req.session and rmb_last:
            values = req.session['disk_ls']
            searchform.formvalues = get_form_values(arguments, values)
        page.content = searchform.form

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
