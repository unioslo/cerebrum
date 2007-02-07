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
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.AllocationPeriodSearchTemplate import AllocationPeriodSearchTemplate
from lib.templates.AllocationPeriodViewTemplate import AllocationPeriodViewTemplate
from lib.templates.AllocationPeriodEditTemplate import AllocationPeriodEditTemplate
from lib.templates.AllocationPeriodCreateTemplate import AllocationPeriodCreateTemplate


def search(transaction, **vargs):
    """Search for allocation periods and displays result and/or searchform."""
    page = Main()
    page.title = _("Search for allocation Period(s)")
    page.setFocus("allocationperiod/search")
    
    handler = SearchHandler('allocationperiod', AllocationPeriodSearchTemplate().form)
    handler.args = ('name', 'allocationauthority')
    handler.headers = (
        ('Name', 'name'), ('Allocation Authority', 'allocationauthority'),
        ('Actions', '')
    )
    
    def search_method(values, offset, orderby, orderby_dir):
        name, allocationauthority = values
        
        searcher = transaction.get_allocation_period_searcher()
        setup_searcher([searcher], orderby, orderby_dir, offset)
        
        if name:
            searcher.set_name_like(name)

        ## XXX need to fix pulldown search for allocation authority
        if allocationauthority:
            searcher.set_allocationauthority_like(allocationauthority)
            
        return searcher.search()

    def row(elm):
        edit = object_link(elm, text='edit', method='edit', _class='action')
        remb = remember_link(elm, _class='action')
        auth = elm.get_authority().get_name()
        return object_link(elm), auth, str(edit)+str(remb)

    objs = handler.search(search_method, **vargs)
    result = handler.get_result(objs, row)
    page.content = lambda: result
    
    return page
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the allocation periods given by id."""
    allocationperiod = transaction.get_allocation_period(int(id))
    page = Main()
    page.title = _('Allocation Period %s') % allocationperiod.get_name()
    page.setFocus('allocationperiod/view', id)
    content = AllocationPeriodViewTemplate().view(transaction, allocationperiod)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True


def edit(transaction, id):
    """Creates a page with the form for editing an allocation period ."""
    allocationperiod = transaction.get_allocation_period(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(allocationperiod)
    page.setFocus("allocationperiod/edit", id)

    authorities = [(a.get_name(), a.get_name()) for a in
               transaction.get_allocation_authority_searcher().search()]

    edit = AllocationPeriodEditTemplate()
    content = edit.editAllocationPeriod(allocationperiod, authorities)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, name, authority, startdate, enddate, submit=None):
    """Saves the information for the host."""
    period = transaction.get_allocation_period(int(id))
    c = transaction.get_commands()

    if submit == 'Cancel':
        redirect_object(host)

    startdate = c.strptime(startdate, "%Y-%m-%d")
    enddate = c.strptime(enddate, "%Y-%m-%d")
    authority = transaction.get_allocation_authority(authority)
    
    period.set_name(name)
    period.set_startdate(startdate)
    period.set_enddate(enddate)
    period.set_authority(authority)
    commit(transaction, period, msg=_("Allocation period successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def create(transaction):
    """Creates a page with the form for creating an allocation period ."""
    page = Main()
    page.title = _("Create a new allocation period")
    page.setFocus("allocationperiod/create")

    authorities = [(a.get_name(), a.get_name()) for a in
               transaction.get_allocation_authority_searcher().search()]

    create = AllocationPeriodCreateTemplate()
    content = create.form(authorities)
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, name, description=""):
    """Creates the host."""
    host = transaction.get_commands().create_host(name, description)
    commit(transaction, host, msg=_("Host successfully created."))
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

