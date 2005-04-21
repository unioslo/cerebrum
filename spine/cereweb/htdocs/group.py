# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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
from Cerebrum import Errors
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect_object, redirect
from Cereweb.utils import object_link, transaction_decorator
from Cereweb.templates.GroupSearchTemplate import GroupSearchTemplate
from Cereweb.templates.GroupViewTemplate import GroupViewTemplate
from Cereweb.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
from Cereweb.templates.GroupEditTemplate import GroupEditTemplate
from Cereweb.templates.GroupCreateTemplate import GroupCreateTemplate

operations = {
    'union':'Union',
    'intersection':'Intersection',
    'difference':'Difference'}

def index(req):
    """Creates a page with the search for group form."""
    page = Main(req)
    page.title = _("Search for group(s):")
    page.setFocus("group/search")
    groupsearch = GroupSearchTemplate()
    page.content = groupsearch.form
    return page

def list(req):
    """Creates a page wich content is the last group-search performed."""
    (name, desc, spread) = req.session.get('group_lastsearch', ("", "", ""))
    return search(req, name, desc, spread)

@transaction_decorator
def search(req, name="", desc="", spread="", transaction=None):
    """Creates a page with a list of groups matching the given criterias."""
    req.session['group_lastsearch'] = (name, desc, spread)
    page = Main(req)
    page.title = _("Search for group(s):")
    page.setFocus("group/list")
    
    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['desc'] = desc
    values['spread'] = spread
    form = GroupSearchTemplate(searchList=[{'formvalues': values}])

    if name or desc or spread:
        server = transaction
        searcher = server.get_group_searcher()
        if name:
            namesearcher = server.get_entity_name_searcher()
            namesearcher.set_name_like(name)
            namesearcher.mark_entity()
            searcher.set_intersections([namesearcher])
        if desc:
            searcher.set_description_like(desc)
        if spread:
            spreadsearcher = server.get_spread_searcher()
            spreadsearcher.set_name_like(spread)
            #hmm, her må det vel litt magi til? spread->entity_spread->entity?
            #iallefall hvis vi skal støtte wildchars i spreadsøket..
            
        groups = searcher.search()

        # Print results
        result = html.Division(_class="searchresult")
        header = html.Header(_("Group search results:"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Group name"), _("Description"), _("Actions"))
        for group in groups:
            view = url("group/view?id=%i" % group.get_id())
            edit = url("group/edit?id=%i" % group.get_id())
            link = html.Anchor(group.get_name(), href=view)
            view = html.Anchor(_('view'), href=view, _class="actions")
            edit = html.Anchor(_('edit'), href=edit, _class="actions")
            table.add(link, group.get_description(), str(view)+str(edit))

        if groups:
            result.append(table)
        else:
            error = "Sorry, no group(s) found matching the given criteria!"
            result.append(html.Division(_(error), _class="searcherror"))

        result = html.Division(result)
        header = html.Header(_("Search for other group(s):"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        result.append(form.form())
        page.content = result.output

    else:
        page.content = form.form

    return page

def _get_group(req, transaction, id):
    """Returns a Group-object from the database with the specific id."""
    try:
        return transaction.get_group(int(id))
    except Exception, e:
        queue_message(req, _("Could not load group with id=%s" % id), error=True)
        queue_message(req, str(e), error=True)
        redirect(req, url("group"), temporary=True)

@transaction_decorator
def view(req, transaction, id):
    """Creates a page with the view of the group with the given by."""
    group = _get_group(req, transaction, id)
    page = Main(req)
    page.title = _("Group %s:" % group.get_name())
    page.setFocus("group/view", str(group.get_id()))
    view = GroupViewTemplate()
    view.add_member = lambda group:_add_box(group)
    content = view.viewGroup(req, group)
    page.content = lambda: content
    return page
    
def _add_box(group):
    ops = operations.items()
    ops.sort()
    ops.reverse()
    member_types = [("account", _("Account")),
                    ("group", _("Group"))]
    action = url("group/add_member?id=%s" % group.get_id())

    template = GroupAddMemberTemplate()
    return template.add_member_box(action, member_types, ops)

@transaction_decorator
def add_member(req, transaction, id, name, type, operation):
    group = _get_group(req, transaction, id)
    try:
        operation = transaction.get_group_member_operation_type(operation)
    except:
        # Display an error-message on top of page.
        queue_message(req, _("%s is not a valid operation.") % 
                           operation, error=True)
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError
    
    try:
        search = transaction.get_entity_name_searcher()
        search.set_name(name)
        search.set_value_domain(transaction.get_value_domain(type + '_names'))
        entityName, = search.search()
        entity = entityName.get_entity()
    except:
        queue_message(req, _("Could not add non-existing member %s %s") %
                         (type, name), error=True)       
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError

    try:
        group.add_member(entity, operation)
    except:    
        queue_message(req, _("Could not add member %s %s to group, "
                      "already member?") % (type, name), error=True) 
    # Display a message stating that entity is added as group-member
    queue_message(req, (_("%s %s added as a member to group.") % 
                        (type, name)))
    redirect_object(req, group, seeOther=True)

    transaction.commit()
    raise Errors.UnreachableCodeError

@transaction_decorator
def remove_member(req, transaction, groupid, memberid, operation):
    group = _get_group(req, transaction, groupid)
    member = transaction.get_entity(int(memberid))
    operation = transaction.get_group_member_operation_type(operation)

    group_member = transaction.get_group_member(group, operation, member, member.get_type())
    group.remove_group_member(group_member)
    queue_message(req, _("%s removed from group %s") % (object_link(member), group))
    redirect_object(req, group, seeOther=True)

    transaction.commit()

def edit(req, id):
    """Creates a page with the form for editing a person."""
    group = _get_group(req, id)
    page = Main(req)
    page.title = _("Edit %s:" % group.get_name())
    page.setFocus("group/edit", str(group.get_id()))
    edit = GroupEditTemplate()
    page.content = lambda: edit.editGroup(req, group)
    return page

def create(req, name="", expire="", description=""):
    """Creates a page with the form for creating a group.

    If names is given, a group is created.
    """
    page = Main(req)
    page.title = _("Create a new group:")
    page.setFocus("group/create")
    
    # Store given parameters in the create-form
    create = GroupCreateTemplate()

    if name:
        server = req.session.get("active")
        page.add_message(_("Sorry, group not create error!"), error=True)
    
    content = create.form(name, expire, description)
    page.content = lambda :content
    return page

def save(req, id, name, expire, description):
    """Save the changes to the server."""
    server = req.session.get("active")
    group = _get_group(req, id)
    
    group.set_name(name)
    group.set_expire_date(server.get_commands().strptime(expire, "%Y-%m-%d"))
    group.set_description(description)

    queue_message(req, _("Group successfully updated."))
    redirect_object(req, group, seeOther=True)

@transaction_decorator
def make(req, transaction, name, expire="", description=""):
    """Performs the creation towards the server."""
    commands = transaction.get_commands()
    group = commands.create_group(name)

    if expire:
        expire = commands.strptime(expire, "%Y-%m-%d")
        group.set_expire_date(expire)

    if description:
        group.set_description(description)
    
    queue_message(req, _("Group successfully created."))
    redirect_object(req, group, seeOther=True)
    transaction.commit()

# arch-tag: d14543c1-a7d9-4c46-8938-c22c94278c34
