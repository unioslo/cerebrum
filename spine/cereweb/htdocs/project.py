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

from account import _get_links()
from gettext import gettext as _
from lib.Main import Main
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.Searchers import ProjectSearcher
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.ProjectViewTemplate import ProjectViewTemplate
from lib.templates.ProjectEditTemplate import ProjectEditTemplate
from lib.templates.ProjectCreateTemplate import ProjectCreateTemplate

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Search for project(s)")
    page.set_focus("project/search")
    page.links = _get_links()

    page.search_fields = [("title", _("Title")),
                          ("description", _("Description")),
                          ("allocation_name", _("Allocation Name")),
                          ("owner", _("Owner")),
                          ("science", _("Science")),
                        ]
    page.search_action = '/project/search'
    page.form_values = remembered
    return page.respond()

def search(transaction, **vargs):
    """Search for projects and displays result and/or searchform."""
    args = ('title', 'description', 'allocation_name', 'science')
    searcher = ProjectSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the project given by id."""
    project = transaction.get_project(int(id))
    page = ProjectViewTemplate()
    page.title = _('Project %s') % project.get_title()
    page.set_focus('project/view')
    page.links = _get_links()
    page.entity = project
    page.entity_id = int(id)
    page.tr = transaction
    return page.respond()
view = transaction_decorator(view)
view.exposed = True

def add_allocation_name(transaction, id, allocation_name, authority):
    project = transaction.get_project(int(id))
    authority = transaction.get_allocation_authority(authority)
    project.add_allocation_name(allocation_name, authority)

    msg = _("Allocation name successfully added.")
    commit(transaction, project, msg=msg)
add_allocation_name = transaction_decorator(add_allocation_name)
add_allocation_name.exposed = True

def remove_allocation_name(transaction, id, allocation_name):
    project = transaction.get_project(int(id))
    project.remove_allocation_name(allocation_name)
    msg = _("Allocation name successfully removed.")
    
    commit(transaction, project, msg=msg)
remove_allocation_name = transaction_decorator(remove_allocation_name)
remove_allocation_name.exposed = True


def edit(transaction, id):
    """Creates a page with the form for editing a project."""
    project = transaction.get_project(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(project)
    page.set_focus("project/edit")

    edit = ProjectEditTemplate()
    content = edit.editProject(project,transaction)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, title="", description="", owner=None,
         science=None, submit=None):
    """Saves the information for the project."""
    project = transaction.get_project(int(id))

    if submit == 'Cancel':
        redirect_object(project)

    project.set_title(title)
    project.set_description(description)
    #XXX project.set_owner(owner)

    project.set_science(transaction.get_science(science))
    commit(transaction, project, msg=_("Project successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def create(transaction, owner, title="", description="", science=None):
    """Creates a page with the form for creating a project"""
    page = Main()
    page.title = _("Create a new project")
    page.set_focus("project/create")

    owner = transaction.get_entity(int(owner))
    
    # Store given create parameters in create-form
    values = {}
    values['title'] = title
    values['description'] = description
    values['owner'] = owner
    values['science'] = science

    create = ProjectCreateTemplate(searchList=[{'formvalues': values}])

    content = create.form(transaction, owner)
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, title="", description="", owner=None, science=None):
    """Creates the project."""

    science = transaction.get_science(science)
    owner = transaction.get_entity(int(owner))

    cmd = transaction.get_commands()
    project = cmd.create_project(owner, science,
                                 title, description)

    commit(transaction, project, msg=_("Project successfully created."))
make = transaction_decorator(make)
make.exposed = True

def delete(transaction, id):
    """Delete the project from the server."""
    project = transaction.get_project(int(id))
    msg = _("Project '%s' successfully deleted.") % project.get_title()
    project.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

