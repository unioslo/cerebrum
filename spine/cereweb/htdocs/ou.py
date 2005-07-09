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

import forgetHTML as html
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator, object_link
from Cereweb.WorkList import remember_link
from Cereweb.templates.OUSearchTemplate import OUSearchTemplate
from Cereweb.templates.OUCreateTemplate import OUCreateTemplate
from Cereweb.templates.OUViewTemplate import OUViewTemplate
from Cereweb.templates.OUEditTemplate import OUEditTemplate


def index(req):
    page = Main(req)
    page.title = _("Search for OU(s):")
    page.setFocus("ou/search")
    ousearcher = OUSearchTemplate()
    page.content = ousearcher.form
    return page

def list(req):
    return search(req, *req.session.get('ou_lastsearch', ()))

def search(req, name="", acronym="", transaction=None):
    req.session['ou_lastsearch'] = (name,)
    page = Main(req)
    page.title = _("Search for OU(s):")
    page.setFocus("ou/search")
    ousearcher = OUSearchTemplate()
    page.content = ousearcher.form

    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['acronym'] = acronym
    form = OUSearchTemplate(searchList=[{'formvalues': values}])

    if name or acronym:
        searcher = transaction.get_ou_searcher()
        if name:
            searcher.set_name_like(name)
        if acronym:
            searcher.set_acronym_like(acronym)
        ous = searcher.search()
    
        # Print results
        result = html.Division(_class="searchresult")
        header = html.Header(_("Organisation Unit search results:"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Name"), _("Acronym"), _("Actions"))
        for ou in ous:
            view = str(object_link(ou, text="view", _class="actions"))
            edit = str(object_link(ou, text="edit", method="edit", _class="actions"))
            remb = str(remember_link(ou, _class="actions"))
            table.add(object_link(ou), ou.get_acronym(), view+edit+remb)
        
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
    page.title = _("OU %s:" % ou.get_name())
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
    content = OUEditTemplate().form(ou)
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
    ou.set_katalog_merke(vargs.get("catalogue_mark", ""))
   
    args = vargs.keys()
    if "countrycode" in args:
        ou.set_landkode(int(vargs["countrycode"]))
    if "institution" in args:
        ou.set_institusjon(int(vargs["institution"]))
    if "faculty" in args:
        ou.set_fakultet(int(vargs["faculty"]))
    if "institute" in args:
        ou.set_institutt(int(vargs["institute"]))
    if "department" in args:
        ou.set_avdeling(int(vargs["department"]))
   
    redirect_object(req, ou, seeOther=True)
    transaction.commit()
    queue_message(req, _("Organization Unit successfully modified."))
save = transaction_decorator(save)

def delete(req, transaction, id):
    ou = transaction.get_ou(int(id))
    #ou.delete()

    #redirect_url(req, "ou", seeOther=True)
    #transaction.commit()
    #queue_message(req, _("Organization Unit successfully deleted."))
    redirect_object(req, ou, seeOther=True)
    queue_message(req, _("Deletion of OU not yet implemented on the server."), error=True)
delete = transaction_decorator(delete)

