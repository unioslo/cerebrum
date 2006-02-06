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
from lib.utils import transaction_decorator, commit_url
from lib.utils import queue_message, redirect
from lib.templates.PermissionsTemplate import PermissionsTemplate

def index(transaction):
    """Form for selecting an operation set, and for creating a new."""
    page = Main()
    page.title = _('Permission Control')
    page.setFocus('permissions')
    
    template = PermissionsTemplate().view_index(transaction)
    page.content = lambda: template
    return page
index = transaction_decorator(index)
index.exposed = True

def view(transaction, id):
    """View the auth operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    page = Main()
    page.title = _('Operation set %s') % op_set.get_name()
    page.setFocus('permissions/view', id)

    template = PermissionsTemplate().view(transaction, op_set)
    page.content = lambda: template
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Edit the auth operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    page = Main()
    page.title = _('Operation set %s') % op_set.get_name()
    page.setFocus('permissions/edit', id)

    template = PermissionsTemplate().edit(op_set)
    page.content = lambda: template
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def delete(transaction, id):
    """Delete the operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    name = op_set.get_name()
    op_set.delete()
    
    msg = _("Operation set %s deleted successfully") % name
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def save(transaction, id, name, description):
    """Saves an updated operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    op_set.set_name(name)
    op_set.set_description(description)
    
    msg = _("Operation set updated successfully.")
    commit_url(transaction, 'view?id=%i' % op_set.get_id(), msg=msg)
save = transaction_decorator(save)
save.exposed = True

def make(transaction, name, description=""):
    """Creates a new operation set."""
    commands = transaction.get_commands()
    op_set = commands.create_auth_operation_set(name, description)
    
    msg = _("Operation set '%s' created successfully.") % name
    commit_url(transaction, 'view?id=%i' % op_set.get_id(), msg=msg)
make = transaction_decorator(make)
make.exposed = True

def update_methods(transaction, id, current):
    op_set = transaction.get_auth_operation_set(int(id))
    old = op_set.get_methods()
update_methods = transaction_decorator(update_methods)
update_methods.exposed = True

def view_user(transaction, id):
    """View the permissions this user has."""
    entity = transaction.get_entity(int(id))
    return _view_user(transaction, entity)
view_user = transaction_decorator(view_user)
view_user.exposed = True

def view_user_by_name(transaction, name, type):
    """Find the user by name and view his permissions."""
    search = transaction.get_entity_name_searcher()
    search.set_name(name)
    search.set_value_domain(transaction.get_value_domain(type + '_names'))
    try:
        entity_name, = search.search()
    except ValueError, e:
        queue_message(_("Could not find %s %s") % (type, name), True)
        redirect('index')
        return
    
    return _view_user(transaction, entity_name.get_entity())
view_user_by_name = transaction_decorator(view_user_by_name)
view_user_by_name.exposed = True

def _view_user(transaction, entity):
    page = Main()
    page.title = _('Permissions for %s') % entity.get_name()
    page.setFocus('permissions')
    template = PermissionsTemplate().view_user(entity)
    page.content = lambda: template
    return page

# arch-tag: 4e5580f4-9764-11da-8677-8396cc25bdc0
