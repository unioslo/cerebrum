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
from Cereweb.utils import url, redirect_object, commit, commit_url
from Cereweb.utils import transaction_decorator, object_link
from Cereweb.WorkList import remember_link
from Cereweb.Search import get_arg_values, get_form_values, setup_searcher
from Cereweb.templates.SearchResultTemplate import SearchResultTemplate
from Cereweb.templates.OUSearchTemplate import OUSearchTemplate
from Cereweb.templates.OUCreateTemplate import OUCreateTemplate
from Cereweb.templates.OUTreeTemplate import OUTreeTemplate
from Cereweb.templates.OUEditTemplate import OUEditTemplate
from Cereweb.templates.OUViewTemplate import OUViewTemplate


def index(req):
    return search(req)

def tree(req, transaction, perspective=None):
    page = Main(req)
    page.title = _("OU perspective tree")
    page.setFocus("ou/tree")
    tree_template = OUTreeTemplate()
    if not perspective:
        perspective = req.session.get("ou_perspective", None)
    else:    
        req.session["ou_perspective"] = perspective    
    if perspective:
        perspective = transaction.get_ou_perspective_type(perspective)
    content = tree_template.viewTree(transaction, perspective)
    page.content = lambda: content
    return page
tree = transaction_decorator(tree)

def search(req, transaction, offset=0, **vargs):
    """Search for ous and displays result and/or searchform."""
    page = Main(req)
    page.title = _("Search for OU(s)")
    page.setFocus("ou/search")
    page.add_jscript("search.js")
    
    searchform = OUSearchTemplate()
    arguments = ['name', 'acronym', 'short', 
                 'spread', 'orderby', 'orderby_dir']
    values = get_arg_values(arguments, vargs)
    perform_search = len([i for i in values if i != ""])
                
    if perform_search:
        req.session['ou_ls'] = values
        name, acronym, short, spread, orderby, orderby_dir = values
        
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

        ous = search.search()
    
        result = []
        display_hits = req.session['options'].getint('search', 'display hits')
        for ou in ous[:display_hits]:
            link = object_link(ou, text=_get_display_name(ou))
            edit = str(object_link(ou, text='edit', method='edit', _class='actions'))
            remb = str(remember_link(ou, _class='actions'))
            result.append((link, ou.get_acronym(), ou.get_short_name(), edit+remb))
       
        headers = [('Name', 'name'), ('Acronym', 'acronym'),
                   ('Short name', 'short_name'), ('Actions', '')]
        
        template = SearchResultTemplate()
        table = template.view(result, headers, arguments, values,
            len(ous), display_hits, offset, searchform, 'ou/search')

        page.content = lambda: table
    else:
        rmb_last = req.session['options'].getboolean('search', 'remember last')
        if 'ou_ls' in req.session and rmb_last:
            values = req.session['ou_ls']
            searchform.formvalues = get_form_values(arguments, values)
        page.content = searchform.form

    return page
search = transaction_decorator(search)

def view(req, transaction, id):
    ou = transaction.get_ou(int(id))
    page = Main(req)
    page.title = _("OU %s") % _get_display_name(ou)
    page.setFocus("ou/view", id)
    content = OUViewTemplate().viewOU(transaction, ou)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    ou = transaction.get_ou(int(id))
    page = Main(req)
    page.title = _("OU ") + object_link(ou)
    page.setFocus("ou/edit", id)
    content = OUEditTemplate().form(transaction, ou)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def create(req, transaction, **vargs):
    page = Main(req)
    page.title = _("Create a new Organization Unit")
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

def make(req, transaction, name, institution,
         faculty, institute, department, **vargs):
    acronym = vargs.get("acronym", "")
    short_name = vargs.get("short_name", "")
    display_name = vargs.get("display_name", "")
    sort_name = vargs.get("sort_name", "")
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
    commit(transaction, req, ou, msg=msg)
make = transaction_decorator(make)

def save(req, transaction, id, name, submit=None, **vargs):
    ou = transaction.get_ou(int(id))

    if submit == "Cancel":
        redirect_object(req, ou, seeOther=True)
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
    commit(transaction, req, ou, msg=msg)
save = transaction_decorator(save)

def delete(req, transaction, id):
    ou = transaction.get_ou(int(id))
    msg =_("OU '%s' successfully deleted.") % _get_display_name(ou)
    ou.delete()
    commit_url(transaction, req, url("ou/index"), msg=msg)
delete = transaction_decorator(delete)

def _get_display_name(ou):
    display_name = ou.get_display_name()
    if display_name:
        return display_name
    else:
        return ou.get_name()

# arch-tag: 6a071cd0-f0bc-11d9-90c5-0c57c7893102
