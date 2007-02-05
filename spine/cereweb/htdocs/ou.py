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
from lib.utils import redirect_object, commit, commit_url
from lib.utils import rollback_url
from lib.utils import transaction_decorator, object_link
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.OUSearchTemplate import OUSearchTemplate
from lib.templates.OUCreateTemplate import OUCreateTemplate
from lib.templates.OUTreeTemplate import OUTreeTemplate
from lib.templates.OUEditTemplate import OUEditTemplate
from lib.templates.OUViewTemplate import OUViewTemplate

def tree(transaction, perspective=None):
    page = Main()
    page.title = _("OU")
    page.setFocus("/ou/tree")
    tree_template = OUTreeTemplate()
    tree_template.title = _('OU perspective tree:')
    if not perspective:
        perspective = cherrypy.session.get("ou_perspective", None)
    else:    
        cherrypy.session["ou_perspective"] = perspective    
    if perspective:
        perspective = transaction.get_ou_perspective_type(perspective)
    content = tree_template.viewTree(transaction, perspective)
    page.content = lambda: content
    return page
tree = transaction_decorator(tree)
tree.exposed = True

def search(transaction, **vargs):
    """Search for ous and displays result and/or searchform."""
    page = Main()
    page.title = _("OU")
    page.setFocus("ou/search")
    page.add_jscript("search.js")
    
    template = OUSearchTemplate()
    template.title = _('OU(s)')
    handler = SearchHandler('ou', template.form)
    handler.args = (
        'name', 'acronym', 'short', 'spread'
    )
    handler.headers = (
        ('Name', 'name'), ('Acronym', 'acronym'),
        ('Short name', 'short_name'), ('Actions', '')
    )
    
    def search_method(values, offset, orderby, orderby_dir):
        name, acronym, short, spread = values
        
        search = transaction.get_ou_searcher()
        setup_searcher([search], orderby, orderby_dir, offset)
        
        if name:
            search.set_name_like(name)
        if acronym:
            search.set_acronym_like(acronym)
        if short:
            search.set_short_name_like(short)
            
        if spread:
            ou_type = transaction.get_entity_type('ou')

            searcher = transaction.get_entity_spread_searcher()
            searcher.set_entity_type(ou_type)

            spreadsearcher = transaction.get_spread_searcher()
            spreadsearcher.set_entity_type(ou_type)
            spreadsearcher.set_name_like(spread)

            searcher.add_join('spread', spreadsearcher, '')
            search.add_intersection('', searcher, 'entity')

        return search.search()
    
    def row(elm):
        link = object_link(elm, text=_get_display_name(elm))
        edit = object_link(elm, text='edit', method='edit', _class='action')
        remb = remember_link(elm, _class='action')
        return link, elm.get_acronym(), elm.get_short_name(), str(edit)+str(remb)
       
    ous = handler.search(search_method, **vargs)
    result = handler.get_result(ous, row)
    page.content = lambda: result

    return page
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    ou = transaction.get_ou(int(id))
    page = Main()
    page.title = _("OU %s") % _get_display_name(ou)
    page.setFocus("ou/view", id)
    content = OUViewTemplate().view(transaction, ou)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    ou = transaction.get_ou(int(id))
    page = Main()
    page.title = _("OU ") + object_link(ou)
    page.setFocus("ou/edit", id)
    content = OUEditTemplate().form(transaction, ou)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def create(transaction, **vargs):
    page = Main()
    page.title = _("OU")
    page.setFocus("ou/create")

    # Store given parameters for the create-form
    values = {}
    values['name'] = vargs.get("name", "")
    values['acronym'] = vargs.get("acronym", "")
    values['short_name'] = vargs.get("short_name", "")
    values['sort_name'] = vargs.get("sort_name", "")

    create = OUCreateTemplate(searchList=[{'formvalues': values}])
    page.content = create.form
    
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, name, institution,
         faculty, institute, department, **vargs):
    acronym = vargs.get("acronym", "")
    short_name = vargs.get("short_name", "")
    display_name = vargs.get("display_name", "")
    sort_name = vargs.get("sort_name", "")

    msg=''
    if not name:
        msg=_('Name is empty.')

    if not msg and not instituion:
        msg=_('Institution is empty.')

    if not msg and not faculty:
        msg=_('Faculty is empty.')

    if not msg and not institute:
        msg=_('Institute is empty.')

    if not msg and not department:
        msg=_('Department is empty.')

    if not msg:
        institution = int(institution)
        faculty = int(faculty)
        institute = int(institute)
        department = int(department)
    
        ou = transaction.get_commands().create_ou(name, institution,
                                        faculty, institute, department)
    
        if acronym:
            ou.set_acronym(acronym)
        if short_name:
            ou.set_short_name(short_name)
        if display_name:
            ou.set_display_name(display_name)
        if sort_name:
            ou.set_sort_name(sort_name)

        msg = _("Organization Unit successfully created.")
        commit(transaction, ou, msg=msg)
    else:
        rollback_url('/ou/create', msg, err=True)
make = transaction_decorator(make)
make.exposed = True

def save(transaction, id, name, submit=None, **vargs):
    ou = transaction.get_ou(int(id))

    if submit == "Cancel":
        redirect_object(ou)
        return

    ou.set_name(name)
    ou.set_acronym(vargs.get("acronym", ""))
    ou.set_short_name(vargs.get("short_name", ""))
    ou.set_display_name(vargs.get("display_name", ""))
    ou.set_sort_name(vargs.get("sort_name", ""))

    if "catalogue_mark" in vargs.keys():
        mark = vargs.get("catalogue_mark")
        ou.set_katalog_merke(mark and True or False)
   
    stedkode_map = {
        'countrycode': ou.set_landkode,
        'institution': ou.set_institusjon,
        'faculty': ou.set_fakultet,
        'institute': ou.set_institutt,
        'department': ou.set_avdeling
    }
        
    parents = {}
    for (key, value) in vargs.items():
        if key in stedkode_map:
            stedkode_map[key](int(value))
        elif key.startswith("parent_"):
            parent = key.replace("parent_", "")
            if value.isdigit():
                # Could also be "root" and "not_in"
                value = int(value)
            parents[parent] = value
    
    for (perspective, parent) in parents.items():
        perspective = transaction.get_ou_perspective_type(perspective)            
        if parent == "root":
            ou.set_parent(None, perspective)
        elif parent == "not_in":
            ou.unset_parent(perspective)
        else:
            parent = transaction.get_ou(parent)     
            ou.set_parent(parent, perspective)
   
    msg = _("Organization Unit successfully modified.")
    commit(transaction, ou, msg=msg)
save = transaction_decorator(save)
save.exposed = True

def delete(transaction, id):
    ou = transaction.get_ou(int(id))
    msg =_("OU '%s' successfully deleted.") % _get_display_name(ou)
    ou.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def _get_display_name(ou):
    display_name = ou.get_display_name()
    if display_name:
        return display_name
    else:
        return ou.get_name()

# arch-tag: 6a071cd0-f0bc-11d9-90c5-0c57c7893102
