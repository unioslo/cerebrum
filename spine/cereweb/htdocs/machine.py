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
from lib.utils import transaction_decorator, redirect, redirect_object, remember_link
from lib.Searchers import HostSearcher
from lib.templates.SearchTemplate import SearchTemplate
# from lib.templates.HostViewTemplate import HostViewTemplate
# from lib.templates.HostEditTemplate import HostEditTemplate
#from lib.templates.HostCreateTemplate import HostCreateTemplate
from lib.templates.MachineViewTemplate import MachineViewTemplate
from lib.templates.MachineEditTemplate import MachineEditTemplate
from lib.templates.MachineCreateTemplate import MachineCreateTemplate

from host import _get_links

def index():
   return search(name='*')
index.exposed = True

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Host")
    page.search_title = _('host(s)')
    page.set_focus("host/search")
    page.links = _get_links

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

def view(transaction, id):
    """Creates a page with a view of the host given by id."""
    host = transaction.get_host(int(id))
    page = MachineViewTemplate()
    page.title = _('Host %s') % host.get_name()
    page.set_focus('host/view')
    page.links = _get_links
    page.entity = host
    page.entity_id = int(id)
    return page.respond()
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a host."""
    host = transaction.get_host(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(host)
    page.set_focus("host/edit")
    page.links = _get_links

    edit = MachineEditTemplate()
    content = edit.editHost(host,transaction)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, name, description="", submit=None, **vargs):
    """Saves the information for the host."""
    host = transaction.get_host(int(id))


    if submit == 'Cancel':
        redirect_object(host)
    
    host.set_name(name)
    host.set_description(description)
    if host.is_machine():
       cpu_arch = vargs.get('cpu_arch')
       operating_system = vargs.get('operating_system')
       interconnect = vargs.get('interconnect')
       total_memory = vargs.get('total_memory')
       node_number = vargs.get('node_number')
       node_memory = vargs.get('node_memory')
       node_disk = vargs.get('node_disk')
       cpu_core_number = vargs.get('cpu_core_number')
       cpu_core_mflops = vargs.get('cpu_core_mflops')
       cpu_mhz = vargs.get('cpu_mhz')

       if total_memory == '':
           total_memory = -1
       if node_number == '':
           node_number = -1
       if node_memory == '':
           node_memory = -1
       if node_disk == '':
           node_disk = -1
       if cpu_core_number == '':
           cpu_core_number = -1
       if cpu_core_mflops == '':
           cpu_core_mflops = -1
       if cpu_mhz == '':
           cpu_mhz = -1

       host.set_cpu_arch(transaction.get_cpu_arch(cpu_arch))    
       host.set_operating_system(transaction.get_operating_system(operating_system))
       host.set_interconnect(transaction.get_interconnect(interconnect))
       host.set_total_memory(int(total_memory))
       host.set_node_number(int(node_number))
       host.set_node_memory(int(node_memory))
       host.set_node_disk(int(node_disk))
       host.set_cpu_core_number(int(cpu_core_number))
       host.set_cpu_core_mflops(int(cpu_core_mflops))
       host.set_cpu_mhz(int(cpu_mhz))
    
    commit(transaction, host, msg=_("Host successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def machine_promote(transaction, id):
    host = transaction.get_host(int(id))
    searcher = transaction.get_cpu_arch_searcher()
    cpu_arch = searcher.search()[0]
    searcher = transaction.get_operating_system_searcher()
    operating_system = searcher.search()[0]
    searcher = transaction.get_interconnect_searcher()
    interconnect = searcher.search()[0]
    host.promote_machine(cpu_arch, operating_system, interconnect)
    msg = _("Host successfully promoted.")
    commit(transaction, host, msg=msg)
    queue_message(_(msg), True, object_link(host))
    redirect_object(host)
machine_promote = transaction_decorator(machine_promote)
machine_promote.exposed = True

def machine_demote(transaction, id):
    host = transaction.get_host(int(id))
    host.demote_machine()
    msg = _("Host successfully demoted.")
    commit(transaction, host, msg=msg)
machine_demote = transaction_decorator(machine_demote)
machine_demote.exposed = True



def create(transaction, name="", description=""):
    """Creates a page with the form for creating a host."""
    page = Main()
    page.title = _("Create a new host")
    page.set_focus("host/create")
    page.links = _get_links

    # Store given create parameters in create-form
    values = {}
    values['name'] = name
    values['description'] = description

    create = MachineCreateTemplate(searchList=[{'formvalues': values}])
    content = create.form(transaction)
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, name, description="", **vargs):
    """Creates the host."""

    cpu_arch = vargs.get('cpu_arch')
    operating_system = vargs.get('operating_system')
    interconnect = vargs.get('interconnect')
    total_memory = vargs.get('total_memory')
    node_number = vargs.get('node_number')
    node_memory = vargs.get('node_memory')
    node_disk = vargs.get('node_disk')
    cpu_core_number = vargs.get('cpu_core_number')
    cpu_core_mflops = vargs.get('cpu_core_mflops')
    cpu_mhz = vargs.get('cpu_mhz')

    host = transaction.get_commands().create_host(name, description)

    host.promote_machine(transaction.get_cpu_arch(cpu_arch), transaction.get_operating_system(operating_system), transaction.get_interconnect(interconnect))

    if total_memory:
       host.set_total_memory(int(total_memory))
    if node_number:
       host.set_node_number(int(node_number))
    if node_memory:
       host.set_node_memory(int(node_memory))
    if node_disk:
       host.set_node_disk(int(node_disk))
    if cpu_core_number: 
       host.set_cpu_core_number(int(cpu_core_number))
    if cpu_core_mflops:
       host.set_cpu_core_mflops(int(cpu_core_mflops))
    if cpu_mhz:
       host.set_cpu_mhz(int(cpu_mhz))

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
