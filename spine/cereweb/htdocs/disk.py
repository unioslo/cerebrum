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
from lib.utils import commit, commit_url, object_link
from lib.utils import transaction_decorator, redirect_object
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.DiskSearchTemplate import DiskSearchTemplate
from lib.templates.DiskViewTemplate import DiskViewTemplate
from lib.templates.DiskEditTemplate import DiskEditTemplate
from lib.templates.DiskCreateTemplate import DiskCreateTemplate

def search(transaction, **vargs):
    """Search after disks and displays result and/or searchform."""
    page = Main()
    page.title = _("Search for disk(s)")
    page.setFocus("disk/search")
    page.add_jscript("search.js")
   
    handler = SearchHandler('disk', DiskSearchTemplate().form)
    handler.args = ('path', 'description')
    handler.headers = (
        ('Path', 'path'), ('Host', ''),
        ('Description', 'description'), ('Actions', '')
    )
   
    def search_method(values, offset, orderby, orderby_dir):
        path, description = values

        disksearcher = transaction.get_disk_searcher()
        setup_searcher([disksearcher], orderby, orderby_dir, offset)

        if path:
            disksearcher.set_path_like(path)

        if description:
            disksearcher.set_description_like(description)
            
        return disksearcher.search()

    def row(elm):
        path = object_link(elm, text=elm.get_path())
        host = object_link(elm.get_host())
        edit = object_link(elm, text='edit', method='edit', _class='action')
        remb = remember_link(elm, _class='action')
        return path, host, elm.get_description(), str(edit)+str(remb)

    disks = handler.search(search_method, **vargs)
    result = handler.get_result(disks, row)
    page.content = lambda: result

    return page
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the disk given by id."""
    disk = transaction.get_disk(int(id))
    page = Main()
    page.title = _('Disk %s') % disk.get_path()
    page.setFocus('disk/view', id)
    content = DiskViewTemplate().view(transaction, disk)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a disk."""
    disk = transaction.get_disk(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(disk)
    page.setFocus("disk/edit", id)

    edit = DiskEditTemplate()
    content = edit.editDisk(disk)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, path="", description="", submit=None):
    """Saves the information for the disk."""
    disk = transaction.get_disk(int(id))

    if submit == 'Cancel':
        redirect_object(disk)
        return
    
    disk.set_path(path)
    disk.set_description(description)
    
    commit(transaction, disk, msg=_("Disk successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def create(transaction, host=""):
    """Creates a page with the form for creating a disk."""
    page = Main()
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
create.exposed = True

def make(transaction, host, path="", description=""):
    """Creates the host."""
    host = transaction.get_host(int(host))
    disk = transaction.get_commands().create_disk(host, path, description)
    commit(transaction, disk, msg=_("Disk successfully created."))
make = transaction_decorator(make)
make.exposed = True

def delete(transaction, id):
    """Delete the disk from the server."""
    disk = transaction.get_disk(int(id))
    msg = _("Disk '%s' successfully deleted.") % disk.get_path()
    disk.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

# arch-tag: 6cf3413e-3bf4-11da-9d43-c8c980cc74d7
