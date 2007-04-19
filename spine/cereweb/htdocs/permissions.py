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
from lib.Forms import RoleCreateForm
from lib.utils import transaction_decorator, commit_url
from lib.utils import queue_message, redirect
from lib.templates.FormTemplate import FormTemplate
from lib.templates.PermissionsTemplate import PermissionsTemplate
from SpineIDL.Errors import NotFoundError

def _get_links():
    return (
        ('/permissions/roles', _('Roles')),
        ('/permissions/targets', _('Targets')),
    )

def roles(transaction):
    """Form for selecting an operation set, and for creating a new."""
    page = PermissionsTemplate()
    page.title = _('Roles')
    page.set_focus('permissions/roles')
    page.links = _get_links()
    page.roles = []
    for role in transaction.get_auth_role_searcher().search():
        e = role.get_entity()
        if e.get_name() in ['cereweb_self', 'cereweb_public', 'cereweb_basic']:
            continue

        t = role.get_target()

        t_type = t.get_type()
        if t_type == 'self':
            continue
        elif t_type == 'global':
            target = 'All'
        else:
            target = t.get_entity().get_name()
            
        o = role.get_op_set()
        r = {
            'g_id': e.get_id(),
            'g_name': e.get_name(),
            't_id': t.get_id(),
            't_name': target,
            'o_id': o.get_id(),
            'o_name': o.get_name(),
            'o_desc': o.get_description(),
        }
        page.roles.append(r)
    return page.respond()
roles = transaction_decorator(roles)
roles.exposed = True
index = roles

def targets(transaction):
    page = Permissions

def view(transaction, id):
    """View the auth operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    page = PermissionsTemplate()
    page.title = _('Operation set %s') % op_set.get_name()
    page.set_focus('permissions/view')
    page.links = _get_links()
    page.add_jscript('permissions.js')
    page.entity = op_set
    page.tr = transaction
    page.entity_id = int(id)

    return page.respond()
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Edit the auth operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    page = Main()
    page.title = _('Operation set %s') % op_set.get_name()
    page.set_focus('permissions/edit')

    template = PermissionsTemplate().edit(op_set)
    page.content = lambda: template
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def add_form(form, message=None):
    page = FormTemplate()
    page.links = _get_links()
    action = {'name': 'View', 'target': '/permissions/roles'}
    if message:
        page.messages.append(message)
    if not action in page.action:
        page.action.append(action)
    page.set_focus('permissions/roles')
    page.form_title = 'Add Role'
    page.form_action = "/permissions/add"
    page.form_fields = form.get_fields()
    return page.respond()                                                                              

def add(transaction, **vargs):
    form = RoleCreateForm(transaction, **vargs)
    if not vargs:
        return add_form(form)
    elif not form.is_correct():
        return add_form(form, message=form.get_error_message())

    searcher = transaction.get_auth_operation_target_searcher()
    target_type = vargs.get('target_type')
    searcher.set_type(target_type)
    if target_type in ['self', 'global']:
        target = None
    else:
        try:
            entity_id = int(vargs.get('target'))
            entity = transaction.get_ou(entity_id)
            searcher.set_entity(entity)
        except NotFoundError, e:
            queue_message(_("Could not find ou %s" % vargs.get('target')), error=True)
            redirect('/permissions/')

    targets = searcher.search()
    if targets:
        target = targets[0]
        if len(targets) > 1:
            print 'DEBUG: More than one target'
    else:
        if target_type == 'self':
            queue_message(_("Creation of 'self' targets not implemented."), error=True)
            redirect('/permissions/')
        elif target_type == 'entity':
            target = transaction.get_commands().create_auth_operation_entity_target(entity, '')
        else:
            target = transaction.get_commands().create_auth_operation_global_target('')

    try:
        gid = int(vargs.get('group'))
        group = transaction.get_group(gid)
    except NotFoundError, e:
        queue_message(_("Could not find group %s" % vargs.get('group')), error=True)
        redirect('/permissions/')

    try:
        op_set = int(vargs.get('op_set'))
        op_set = transaction.get_auth_operation_set(op_set)
    except NotFoundError, e:
        queue_message(_("Could not find op_set %s" % vargs.get('op_set')), error=True)
        redirect('/permissions/')

    try:
        transaction.get_commands().create_auth_role(group, op_set, target)
    except:
        queue_message(_("Could not create auth_role %s, %s, %s" % (gid, vargs.get('op_set'), target.get_id())), error=True)
        redirect('/permissions/')
    msg = _("Created auth_role.")
    commit_url(transaction, 'index', msg=msg)

add = transaction_decorator(add)
add.exposed = True


def delete(transaction, **vargs):
    """Delete the role."""
    g = int(vargs.get('g'))
    o = int(vargs.get('o'))
    t = int(vargs.get('t'))
    if g and o and t:
        try:
            group = transaction.get_entity(g)
            op_set = transaction.get_auth_operation_set(o)
            target = transaction.get_auth_operation_target(t)
            role = transaction.get_auth_role(group, op_set, target)
        except NotFoundError, e:
            queue_message(_("Could not find auth_role %s, %s, %s" % (g, o, t)), error=True)
            redirect('/permissions/')
        role.delete()
        msg = _("Auth role deleted successfully.")
        commit_url(transaction, 'index', msg=msg)
    else:
        redirect('/permissions/')
delete = transaction_decorator(delete)
delete.exposed = True

def users(transaction, id):
    """View users on the op set."""
    op_set = transaction.get_auth_operation_set(int(id))
    page = Main()
    page.title = _('Users on %s') % op_set.get_name()
    page.set_focus('permissions/users')

    template = PermissionsTemplate().users(transaction, op_set)
    page.content = lambda: template
    return page
users = transaction_decorator(users)
users.exposed = True

def save(transaction, id, name, description):
    """Saves an updated operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
#    op_set.set_name(name)
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

def update_methods(transaction, id, **vargs):
    """Update methods on operation set."""
    op_set = transaction.get_auth_operation_set(int(id))
    
    new = [int(i.split('.')[2]) for i in vargs.get('current', ()) if '.' in i]
   
    # Remove old operations
    for op in op_set.get_operations():
        id = op.get_id()
        if id not in new:
            op_set.remove_operation(op)
        else:
            new.remove(id)

    # Add new operations.
    for id in new:
        op_set.add_operation(transaction.get_auth_operation_code(id))

    msg = _("Operation set '%s' updated successfully.") % op_set.get_name()
    commit_url(transaction, 'view?id=%i' % op_set.get_id(), msg=msg)
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
    page.set_focus('permissions/')
    template = PermissionsTemplate().view_user(entity)
    page.content = lambda: template
    return page

def get_all_operations(transaction):
    """Return a javascript JSON array with all operations."""
    ops = {}
    for op in transaction.get_auth_operation_code_searcher().search():
        cls = op.get_op_class()
        if cls not in ops.keys():
            ops[cls] = [(op.get_op_method(), op.get_id())]
        else:
            ops[cls].append((op.get_op_method(), op.get_id()))
     
    classes = ops.keys()
    classes.sort()
    
    json = []
    for cls in classes:
        methods = []
        for method, id in ops[cls]:
            methods.append("{'name': '%s', 'id': '%s'}" % (method, id))
        json.append("{'cls': '%s', 'methods': [%s]}" % (cls, ", ".join(methods)))
        
    classes = "'" + "', '".join(classes) + "'"
    return "{'classes': [%s], 'methods': [%s]}" % (classes, ", ".join(json))
get_all_operations = transaction_decorator(get_all_operations)
get_all_operations.exposed = True

# arch-tag: 4e5580f4-9764-11da-8677-8396cc25bdc0
