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
from mx import DateTime
from Cerebrum import Errors
from Cerebrum.web.Main import Main
from Cerebrum.web.utils import url
from Cerebrum.web.utils import queue_message
from Cerebrum.web.utils import redirect_object
from Cerebrum.web.utils import redirect
from Cerebrum.web.utils import no_cache
from Cerebrum.web import ServerConnection
from Cerebrum.web.templates.GroupSearchTemplate import GroupSearchTemplate
from Cerebrum.web.templates.GroupViewTemplate import GroupViewTemplate
from Cerebrum.web.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
from Cerebrum.web.templates.GroupEditTemplate import GroupEditTemplate
from Cerebrum.web.templates.GroupCreateTemplate import GroupCreateTemplate


def index(req):
    """Creates a page with the search for group form."""
    page = Main(req)
    page.title = _("Search for group(s):")
    page.menu.setFocus("group/search")
    groupsearch = GroupSearchTemplate()
    page.content = groupsearch.form
    return page

def list(req):
    """Creates a page wich content is the last group-search performed."""
    no_cache(req)
    (name, desc, spread) = req.session.get('group_lastsearch', ("", "", ""))
    return search(req, name, desc, spread)

def search(req, name="", desc="", spread=""):
    """Creates a page with a list of groups matching the given criterias."""
    req.session['group_lastsearch'] = (name, desc, spread)
    page = Main(req)
    page.title = _("Search for group(s):")
    page.menu.setFocus("group/list")
    
    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['desc'] = desc
    values['spread'] = spread
    form = GroupSearchTemplate(searchList=[{'formvalues': values}])

    if name or desc or spread:
        server = ServerConnection.get_server(req)
        searcher = server.get_group_search()
        if name:
            searcher.set_name(name)
        if desc:
            searcher.set_description(desc)
        if spread:
            pass
        groups = searcher.search()

        # Print results
        result = html.Division(_class="searchresult")
        header = html.Header(_("Group search results:"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Group name"), _("Description"), _("Actions"))
        for group in groups:
            view = url("group/view?id=%i" % group.get_entity_id())
            edit = url("group/edit?id=%i" % group.get_entity_id())
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

def _get_group(req, id):
    """Returns a Group-object from the database with the specific id."""
    server = ServerConnection.get_server(req)
    try:
        return server.get_group(int(id))
    except Exception, e:
        queue_message(req, _("Could not load group with id=%s") % id, 
                      error=True)
        queue_message(req, str(e), error=True)
        # Go back to the root of groups, raise redirect-error.
        redirect(req, url("group"), temporary=True)
        raise Errors.UnreachableCodeError

def view(req, id):
    """Creates a page with the view of the group with the given by."""
    group = _get_group(req, id)
    page = Main(req)
    page.title = _("Group %s:" % group.get_name())
    page.menu.setFocus("group/view", str(group.get_entity_id()))
    view = GroupViewTemplate()
    view.add_member = lambda group:_add_box(group)
    page.content = lambda: view.viewGroup(req, group)
    return page
    
def _add_box(group):
    operations = [('union',)*2, ('intersection',)*2, ('difference',)*2]
    member_types = [("account", _("Account")),
                    ("group", _("Group"))]
    action = url("group/add_member?id=%s" % group.get_entity_id())

    template = GroupAddMemberTemplate()
    return template.add_member_box(action, member_types, operations)

def add_member(req, id, name, type, operation):
    server = ServerConnection.get_server(req)
    group = _get_group(req, id)
    if operation not in (ClientAPI.Constants.UNION, 
                         ClientAPI.Constants.INTERSECTION, 
                         ClientAPI.Constants.DIFFERENCE):
        # Display an error-message on top of page.
        queue_message(req, _("%s is not a valid operation.") % 
                           operation, error=True)
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError
    
    try:
        if (type == "account"):
            entity = ClientAPI.Account.fetch_by_name(server, name)
        elif (type == "group"):
            entity = ClientAPI.Group.fetch_by_name(server, name)
    except:
        queue_message(req, _("Could not add non-existing member %s %s") %
                         (type, name), error=True)       
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError

    #FIXME: Operation should be constants somewhere
    try:
        group.add_member(entity, operation)
    except:    
        queue_message(req, _("Could not add member %s %s to group, "
                      "already member?") % (type, name), error=True) 
    # Display a message stating that entity is added as group-member
    queue_message(req, (_("%s %s added as a member to group.") % 
                        (type, name)))
    redirect_object(req, group, seeOther=True)
    raise Errors.UnreachableCodeError

def remove_member(req, groupid, memberid, operation):
    group = _get_group(req, groupid)
    group.remove_member(member_id=memberid, operation=operation)
    queue_message(req, _("%s removed from group %s") % (memberid, group))
    redirect_object(req, group, seeOther=True)
    raise Errors.UnreachableCodeError

def edit(req, id):
    """Creates a page with the form for editing a person."""
    group = _get_group(req, id)
    page = Main(req)
    page.title = _("Edit %s:" % group.get_name())
    page.menu.setFocus("group/edit", str(group.get_entity_id()))
    edit = GroupEditTemplate()
    page.content = lambda: edit.editGroup(req, group)
    return page

def create(req, name="", expiration="", description=""):
    """Creates a page with the form for creating a group.

    If names is given, a group is created.
    """
    page = Main(req)
    page.title = _("Create a new group:")
    page.menu.setFocus("group/create")
    
    # Store given parameters in the create-form
    values = {}
    values['name'] = name
    values['expiration'] = expiration
    values['description'] = description
    create = GroupCreateTemplate(searchList=[{'formvalues': values}])

    if name:
        server = ServerConnection.get_server(req)
        page.add_message(_("Sorry, group not create error!"), error=True)
    
    page.content = create.form
    return page

# arch-tag: d14543c1-a7d9-4c46-8938-c22c94278c34
