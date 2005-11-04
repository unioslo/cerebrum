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
from Cereweb.utils import url, queue_message, redirect_object, commit
from Cereweb.utils import object_link, transaction_decorator, commit_url
from Cereweb.WorkList import remember_link
from Cereweb.Search import get_arg_values, get_form_values, setup_searcher
from Cereweb.templates.SearchResultTemplate import SearchResultTemplate
from Cereweb.templates.GroupSearchTemplate import GroupSearchTemplate
from Cereweb.templates.GroupViewTemplate import GroupViewTemplate
from Cereweb.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
from Cereweb.templates.GroupEditTemplate import GroupEditTemplate
from Cereweb.templates.GroupCreateTemplate import GroupCreateTemplate

import Cereweb.config
display_hits = Cereweb.config.conf.getint('cereweb', 'display_hits')

operations = {
    'union':'Union',
    'intersection':'Intersection',
    'difference':'Difference'}

def index(req):
    """Redirects to the page with search for groups."""
    return search(req)

def search(req, transaction, offset=0, **vargs):
    """Search for groups and displays results and/or searchform."""
    page = Main(req)
    page.title = _("Search for group(s)")
    page.setFocus("group/search")
    page.add_jscript("search.js")
    page.add_jscript("groupsearch.js")
    
    searchform = GroupSearchTemplate()
    arguments = ['name', 'description', 'spread', 'gid', 
                 'gid_end', 'gid_option', 'orderby', 'orderby_dir']
    values = get_arg_values(arguments, vargs)
    perform_search = len([i for i in values if i != ""])
            
    if perform_search:
        req.session['group_ls'] = values
        (name, description, spread, gid, gid_end,
                gid_option, orderby, orderby_dir) = values
        
        search = transaction.get_group_searcher()
        setup_searcher([search], orderby, orderby_dir, offset)
        
        if name:
            search.set_name_like(name)
        if description:
            search.set_description_like(description)
        if gid:
            if gid_option == "exact":
                search.set_posix_gid(int(gid))
            elif gid_option == "above":
                search.set_posix_gid_more_than(int(gid))
            elif gid_option == "below":
                search.set_posix_gid_less_than(int(gid))
            elif gid_option == "range":
                search.set_posix_gid_more_than(int(gid))
                if gid_end:
                    search.set_posix_gid_less_than(int(gid_end))
                
        if spread:
            group_type = transaction.get_entity_type('group')

            searcher = transaction.get_entity_spread_searcher()
            searcher.set_entity_type(group_type)

            spreadsearcher = transaction.get_spread_searcher()
            spreadsearcher.set_entity_type(group_type)
            spreadsearcher.set_name_like(spread) 
            
            searcher.add_join('spread', spreadsearcher, '')
            search.add_intersection('', searcher, 'entity')

        groups = search.search()

        result = []
        for group in groups[:display_hits]:
            edit = str(object_link(group, text='edit', method='edit', _class='actions'))
            remb = str(remember_link(group, _class='actions'))
            result.append((object_link(group), group.get_description(), edit+remb))

        headers = [('Group name', 'name'), ('Description', 'description'),
                   ('Actions', '')]
        table = SearchResultTemplate().view(result, headers, arguments,
                    values, len(groups), offset, searchform, 'group/search')

        page.content = lambda: table
    else:
        if 'group_ls' in req.session:
            values = req.session['group_ls']
            searchform.formvalues = get_form_values(arguments, values)
        page.content = searchform.form

    return page
search = transaction_decorator(search)

def view(req, transaction, id):
    """Creates a page with the view of the group with the given by."""
    group = transaction.get_group(int(id))
    page = Main(req)
    page.title = _("Group %s" % group.get_name())
    page.setFocus("group/view", id)
    view = GroupViewTemplate()
    view.add_member = lambda group:_add_box(group)
    content = view.viewGroup(transaction, group)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
    
def _add_box(group):
    ops = operations.items()
    ops.sort()
    ops.reverse()
    member_types = [("account", _("Account")),
                    ("group", _("Group"))]
    action = url("group/add_member?id=%s" % group.get_id())

    template = GroupAddMemberTemplate()
    return template.add_member_box(action, member_types, ops)

def add_member(req, transaction, id, name, type, operation):
    group = transaction.get_group(int(id))
    
    try:
        op = transaction.get_group_member_operation_type(operation)
    except:
        queue_message(req, _("Invalid operation '%s'.") % operation, True)
        redirect_object(req, group, seeOther=True)
        return
    
    search = transaction.get_entity_name_searcher()
    search.set_name(name)
    search.set_value_domain(transaction.get_value_domain(type + '_names'))
    try:
        entity_name, = search.search()
    except ValueError, e:
        queue_message(req, _("Could not find %s %s") % (type, name), True)
        redirect_object(req, group, seeOther=True)
        return
    
    entity = entity_name.get_entity()
    group.add_member(entity, op)
    
    msg = _("%s added as a member to group.") % object_link(entity)
    commit(transaction, req, group, msg=msg)
add_member = transaction_decorator(add_member)

def remove_member(req, transaction, groupid, memberid, operation):
    group = transaction.get_group(int(groupid))
    member = transaction.get_entity(int(memberid))
    operation = transaction.get_group_member_operation_type(operation)

    group_member = transaction.get_group_member(group, operation, member, member.get_type())
    group.remove_member(group_member)

    msg = _("%s removed from group.") % object_link(member)
    commit(transaction, req, group, msg=msg)
remove_member = transaction_decorator(remove_member)

def edit(req, transaction, id):
    """Creates a page with the form for editing a person."""
    group = transaction.get_group(int(id))
    page = Main(req)
    page.title = _("Edit ") + object_link(group)
    page.setFocus("group/edit", id)

    edit = GroupEditTemplate()
    content = edit.editGroup(transaction, group)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def create(req, name="", expire="", description=""):
    """Creates a page with the form for creating a group."""
    page = Main(req)
    page.title = _("Create a new group")
    page.setFocus("group/create")
    
    content = GroupCreateTemplate().form(name, expire, description)
    page.content = lambda :content
    return page

def save(req, transaction, id, name, expire="",
         description="", visi="", gid=None, submit=None):
    """Save the changes to the server."""
    group = transaction.get_group(int(id))
    c = transaction.get_commands()
    
    if submit == 'Cancel':
        redirect_object(req, group, seeOther=True)
        return
    
    if expire:
        expire = c.strptime(expire, "%Y-%m-%d")
    else:
        if group.get_expire_date():
            expire = c.get_date_none()
            group.set_expire_date(expire)

    if gid is not None and group.is_posix():
        group.set_posix_gid(int(gid))

    if visi:
        visibility = transaction.get_group_visibility_type(visi)
        group.set_visibility(visibility)

    group.set_name(name)
    group.set_description(description)
    
    commit(transaction, req, group, msg=_("Group successfully updated."))
save = transaction_decorator(save)

def make(req, transaction, name, expire="", description=""):
    """Performs the creation towards the server."""
    commands = transaction.get_commands()
    group = commands.create_group(name)

    if expire:
        expire = commands.strptime(expire, "%Y-%m-%d")
        group.set_expire_date(expire)

    if description:
        group.set_description(description)
    
    commit(transaction, req, group, msg=_("Group successfully created."))
make = transaction_decorator(make)

def posix_promote(req, transaction, id):
    group = transaction.get_group(int(id))
    group.promote_posix()
    msg = _("Group successfully promoted to posix.")
    commit(transaction, req, group, msg=msg)
posix_promote = transaction_decorator(posix_promote)

def posix_demote(req, transaction, id):
    group = transaction.get_group(int(id))
    group.demote_posix()
    msg = _("Group successfully demoted from posix.")
    commit(transaction, req, group, msg=msg)
posix_demote = transaction_decorator(posix_demote)

def delete(req, transaction, id):
    """Delete the group from the server."""
    group = transaction.get_group(int(id))
    msg = _("Group '%s' successfully deleted.") % group.get_name()
    group.delete()
    commit_url(transaction, req, url("group/index"), msg=msg)
delete = transaction_decorator(delete)

# arch-tag: d14543c1-a7d9-4c46-8938-c22c94278c34
