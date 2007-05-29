# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
from lib.utils import commit, commit_url, queue_message, object_link, remember_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.Searchers import AllocationSearcher
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.AllocationViewTemplate import AllocationViewTemplate
from lib.templates.AllocationEditTemplate import AllocationEditTemplate
from lib.templates.AllocationCreateTemplate import AllocationCreateTemplate

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Search for allocation(s)")
    page.set_focus("allocation/search")
    page.links = _get_links()
    page.search_fields = [("allocation_name", _("Allocation Name")),
                          ("period", _("Period")),
                          ("machine", _("Machine"))
                        ]
    page.search_action = '/allocation/search'
    page.form_values = remembered
    return page.respond()

def search(transaction, **vargs):
    """Search for allocations and displays result and/or searchform."""
    args = ('allocation_name', 'period', 'status', 'machines')
    searcher = AllocationSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the allocation given by id."""
    allocation = transaction.get_allocation(int(id))
    page = AllocationViewTemplate()
    page.title = _('Allocation %s %s') % (
        allocation.get_allocation_name().get_name(),
        allocation.get_period().get_name() )
    page.set_focus('allocation/view')
    page.links = _get_links()
    page.entity_id = int(id)
    page.entity = allocation
    page.tr = transaction
    return page.respond()
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a allocation."""
    allocation = transaction.get_allocation(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(allocation)
    page.set_focus("allocation/edit")
    page.links = _get_links()

    edit = AllocationEditTemplate()
    content = edit.editAllocation(allocation,transaction)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, title="", description="", owner=None,
         science=None, submit=None):
    """Saves the information for the allocation."""
    allocation = transaction.get_allocation(int(id))

    if submit == 'Cancel':
        redirect_object(allocation)

    #XXX allocation.set_allocation_name( XXX...)
    #XXX allocation.set_period(period)

    allocation.set_status(transaction.get_allocation_status(status))
    commit(transaction, allocation, msg=_("Allocation successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def create(transaction, project=None, allocation_name=None):
    """Creates a page with the form for creating a allocation"""
    page = Main()
    page.title = _("Create a new allocation")
    page.set_focus("allocation/create")
    page.links = _get_links()

    # Store given create parameters in create-form
    values = {}

    create = AllocationCreateTemplate(searchList=[{'formvalues': values}])

    content = create.form(transaction, project, allocation_name)
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, project=None, allocation_name="", period=None, status=None, credits=0):
    """Creates the allocation."""

    status = transaction.get_allocation_status(status)
    
    cmd = transaction.get_commands()
    allocation = cmd.create_allocation(authority, allocation_name, period, status)

    commit(transaction, host, msg=_("Allocation successfully created."))
make = transaction_decorator(make)
make.exposed = True

def delete(transaction, id):
    """Delete the allocation from the server."""
    allocation = transaction.get_allocation(int(id))
    msg = _("Allocation '%s' successfully deleted.") % allocation.get_title()
    allocation.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

