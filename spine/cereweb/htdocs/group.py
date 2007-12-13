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
import string

from account import _get_links
from gettext import gettext as _
from lib.Main import Main
from lib.utils import queue_message, redirect_object, commit
from lib.utils import object_link, transaction_decorator, commit_url
from lib.utils import rollback_url, legal_date, remember_link
from lib.Searchers import GroupSearcher
from lib.templates.GroupSearchTemplate import GroupSearchTemplate
from lib.templates.GroupViewTemplate import GroupViewTemplate
from lib.templates.GroupEditTemplate import GroupEditTemplate
from lib.templates.GroupCreateTemplate import GroupCreateTemplate
from SpineIDL.Errors import NotFoundError, AlreadyExistsError, ValueError

def search_form(remembered):
    page = GroupSearchTemplate()
    page.title = _("Group")
    page.search_title = _('group(s)')   
    page.set_focus("group/search")
    page.links = _get_links()
    page.jscripts.append("groupsearch.js")
    page.search_fields = [("name", _("Name")),
                          ("description", _("Description")),
                          ("spread", _("Spread name")),
                          ]
    page.search_action = '/group/search'
    page.form_values = remembered
    return page.respond()

def search(transaction, **vargs):
    """Search for groups and displays results and/or searchform."""
    args = ('name', 'description', 'spread', 'gid', 'gid_end', 'gid_option')
    searcher = GroupSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id, **vargs):
    """Creates a page with the view of the group with the given by."""
    group = transaction.get_group(int(id))
    page = GroupViewTemplate()
    page.title = _('Group %s') % group.get_name()
    page.set_focus('group/view')
    page.links = _get_links()
    page.entity_id = int(id)
    page.entity = group
    page.tr = transaction
    return page.respond()
view = transaction_decorator(view)
view.exposed = True
    
def add_member(transaction, id, name, type, operation):
    group = transaction.get_group(int(id))
    cmd = transaction.get_commands()
    
    try:
        op = transaction.get_group_member_operation_type(operation)
    except:
        queue_message(_("Invalid operation '%s'.") % operation, True)
        redirect_object(group)
        return
    
    search = transaction.get_entity_name_searcher()
    search.set_name(name)
    search.set_value_domain(cmd.get_namespace(type))
    try:
        entity_name, = search.search()
    except ValueError, e:
        queue_message(_("Could not find %s %s") % (type, name), True)
        redirect_object(group)
        return
    
    entity = entity_name.get_entity()
    group.add_member(entity, op)
    
    msg = _("%s added as a member to group.") % object_link(entity)
    commit(transaction, group, msg=msg)
add_member = transaction_decorator(add_member)
add_member.exposed = True

def remove_member(transaction, groupid, memberid, operation='union'):
    group = transaction.get_group(int(groupid))
    member = transaction.get_entity(int(memberid))
    operation = transaction.get_group_member_operation_type(operation)

    group_member = transaction.get_group_member(group, operation, member, member.get_type())
    group.remove_member(group_member)

    msg = _("%s removed from group.") % object_link(member)
    commit(transaction, group, msg=msg)
remove_member = transaction_decorator(remove_member)
remove_member.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a person."""
    group = transaction.get_group(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(group)
    page.set_focus('group/edit')
    page.links = _get_links()

    edit = GroupEditTemplate()
    content = edit.editGroup(transaction, group)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def create(name="", expire="", description=""):
    """Creates a page with the form for creating a group."""
    page = Main()
    page.title = _("Group")
    page.set_focus('group/create')
    page.links = _get_links()
    
    content = GroupCreateTemplate().form(name, expire, description)
    page.content = lambda :content
    return page
create.exposed = True

def save(transaction, id, name, expire="",
         description="", visi="", gid=None, submit=None):
    """Save the changes to the server."""
    group = transaction.get_group(int(id))
    c = transaction.get_commands()
    
    if submit == 'Cancel':
        redirect_object(group)
        return
    
    if expire:
        expire = c.strptime(expire, "%Y-%m-%d")
    else:
	expire = None
    group.set_expire_date(expire)

    if gid is not None and group.is_posix():
        group.set_posix_gid(int(gid))

    if visi:
        visibility = transaction.get_group_visibility_type(visi)
        group.set_visibility(visibility)

    group.set_name(name)
    group.set_description(description)
    
    commit(transaction, group, msg=_("Group successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def make(transaction, name, expire="", description=""):
    """Performs the creation towards the server."""
    msg=''
    if name:
        if len(name) < 3:
            msg=_("Group-name is too short( min. 3 characters).")
        elif len(name) > 16:
            msg=_("Group-name is too long(max. 16 characters).")
    else:
        msg=_("Group-name is empty.")
    if not msg and expire:
        if not legal_date( expire ):
            msg=_("Expire-date is not a legal date.")
    if not msg:
        commands = transaction.get_commands()
        try:
            group = commands.create_group(name)
        except ValueError, e:
            msg = _("Group '%s' already exists.") % name
    if not msg:    
        if expire:
            expire = commands.strptime(expire, "%Y-%m-%d")
            group.set_expire_date(expire)

        if description:
            group.set_description(description)
        commit(transaction, group, msg=_("Group successfully created."))
    else:
        rollback_url('/group/create', msg, err=True)
make = transaction_decorator(make)
make.exposed = True

def posix_promote(transaction, id):
    group = transaction.get_group(int(id))
    group.promote_posix()
    msg = _("Group successfully promoted to posix.")
    commit(transaction, group, msg=msg)
posix_promote = transaction_decorator(posix_promote)
posix_promote.exposed = True

def posix_demote(transaction, id):
    group = transaction.get_group(int(id))
    group.demote_posix()
    msg = _("Group successfully demoted from posix.")
    commit(transaction, group, msg=msg)
posix_demote = transaction_decorator(posix_demote)
posix_demote.exposed = True

def delete(transaction, id):
    """Delete the group from the server."""
    group = transaction.get_group(int(id))
    msg = _("Group '%s' successfully deleted.") % group.get_name()
    group.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def join_group(transaction, entity, name, operation=None):
    """Join entity into group with name 'group'."""
    entity = transaction.get_entity(int(entity))
    if not operation:
        operation = 'union'
    operation = transaction.get_group_member_operation_type(operation)

    try:
        # find the group by name.
        group = transaction.get_commands().get_group_by_name(name)
        group.add_member(entity, operation)
    except NotFoundError, e:
        msg = _("Group '%s' not found") % name
        queue_message(msg, True, object_link(entity))
        redirect_object(entity)
    except AlreadyExistsError, e:
        msg = _("Entity is already a member of group %s") % name
        queue_message(msg, True, object_link(entity))
        redirect_object(entity)
    except: 
        msg = _("Entity %s could not join group %s") % (entity.get_name(), name)
        queue_message(msg, True, object_link(entity))
        redirect_object(entity)

    msg = _('Joined group %s successfully') % name
    commit(transaction, entity, msg=msg)
join_group = transaction_decorator(join_group)
join_group.exposed = True

# arch-tag: d14543c1-a7d9-4c46-8938-c22c94278c34
