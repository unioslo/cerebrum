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

import sets
import forgetHTML as html
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator, object_link
from Cereweb.WorkList import remember_link
from Cereweb.templates.OUSearchTemplate import OUSearchTemplate
from Cereweb.templates.OUCreateTemplate import OUCreateTemplate
from Cereweb.templates.OUTreeTemplate import OUTreeTemplate
from Cereweb.templates.OUEditTemplate import OUEditTemplate
from Cereweb.templates.OUViewTemplate import OUViewTemplate


def index(req):
    page = Main(req)
    page.title = _("Search for OU(s):")
    page.setFocus("ou/search")
    ousearcher = OUSearchTemplate()
    page.content = ousearcher.form
    return page

def list(req):
    return search(req, *req.session.get('ou_lastsearch', ()))

def tree(req, transaction, perspective=None):
    page = Main(req)
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


def search(req, name="", acronym="", short="", spread="", transaction=None):
    req.session['ou_lastsearch'] = (name, acronym, short, spread)
    page = Main(req)
    page.title = _("Search for OU(s):")
    page.setFocus("ou/search")
    ousearcher = OUSearchTemplate()
    page.content = ousearcher.form

    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['acronym'] = acronym
    values['short'] = short
    values['spread'] = spread
    form = OUSearchTemplate(searchList=[{'formvalues': values}])

    if name or acronym or short or spread:
        searcher = transaction.get_ou_searcher()
        if name:
            searcher.set_name_like(name)
        if acronym:
            searcher.set_acronym_like(acronym)
        if short:
            searcher.set_short_name_like(short)
            
        if spread:
            ous = sets.Set()
            spreadsearcher = transaction.get_spread_searcher()
            spreadsearcher.set_name_like(spread)
            for spread in spreadsearcher.search():
                s = transaction.get_entity_spread_searcher()
                s.set_spread(spread)
                s.mark_entity()
                searcher.set_intersections([s])

                ous.update(searcher.search())
            
        else:
            ous = searcher.search()
    
        # Print results
        result = html.Division(_class="searchresult")
        header = html.Header(_("Organisation Unit search results:"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Name"), _("Acronym"), _("Short name"), _("Actions"))
        for ou in ous:
            link = object_link(ou, text=_get_display_name(ou))
            view = str(object_link(ou, text="view", _class="actions"))
            edit = str(object_link(ou, text="edit", method="edit", _class="actions"))
            remb = str(remember_link(ou, _class="actions"))
            table.add(link, ou.get_acronym(), ou.get_short_name(), view+edit+remb)
        
        if ous:
            result.append(table)
        else:
            error = _("Sorry, no OU(s) found matching the given criteria!")
            result.append(html.Division(error, _class="searcherror"))
        
        result = html.Division(result)
        header = html.Header(_("Search for other OU(s):"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        result.append(form.form())
        page.content = result.output
    
    else:
        page.content = form.form
    
    return page
search = transaction_decorator(search)

def view(req, transaction, id):
    ou = transaction.get_ou(int(id))
    page = Main(req)
    page.title = _("OU %s:" % _get_display_name(ou))
    page.setFocus("ou/view", str(ou.get_id()))
    content = OUViewTemplate().viewOU(transaction, ou)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    ou = transaction.get_ou(int(id))
    page = Main(req)
    page.title = _("OU %s:" % ou.get_name())
    page.setFocus("ou/edit", str(ou.get_id()))
    content = OUEditTemplate().form(transaction, ou)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def create(req, transaction, **vargs):
    page = Main(req)
    page.title = _("Create a new Organization Unit:")
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

    redirect_object(req, ou, seeOther=True)
    transaction.commit()
    queue_message(req, _("Organization Unit successfully created."))
make = transaction_decorator(make)

def save(req, transaction, id, name, **vargs):
    ou = transaction.get_ou(int(id))

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
   
    redirect_object(req, ou, seeOther=True)
    transaction.commit()
    queue_message(req, _("Organization Unit successfully modified."))
save = transaction_decorator(save)

def delete(req, transaction, id):
    ou = transaction.get_ou(int(id))
    ou.delete()

    redirect(req, url("ou"), seeOther=True)
    transaction.commit()
    queue_message(req, _("Organization Unit successfully deleted."))
delete = transaction_decorator(delete)

def _get_display_name(ou):
    display_name = ou.get_display_name()
    if display_name:
        return display_name
    else:
        return ou.get_name()

# arch-tag: 6a071cd0-f0bc-11d9-90c5-0c57c7893102
