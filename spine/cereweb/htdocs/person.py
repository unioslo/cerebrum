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

import time
import forgetHTML as html
from gettext import gettext as _
from Cerebrum.extlib import sets
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator
from Cereweb.templates.PersonSearchTemplate import PersonSearchTemplate
from Cereweb.templates.PersonViewTemplate import PersonViewTemplate
from Cereweb.templates.PersonEditTemplate import PersonEditTemplate
from Cereweb.templates.PersonCreateTemplate import PersonCreateTemplate


def index(req):
    """Creates a page with the search for person form."""
    page = Main(req)
    page.title = _("Search for person(s):")
    page.setFocus("person/search")
    personsearch = PersonSearchTemplate()
    page.content = personsearch.form
    return page

def list(req):
    """Creates a page wich content is the last search performed."""
    (fullname, firstname, lastname,  accountname, birthdate) = \
        req.session.get('person_lastsearch', ("", "", "", "", ""))
    return search(req, fullname, firstname, lastname, accountname, birthdate)

@transaction_decorator
def search(req, fullname="", firstname="", lastname="", accountname="", birthdate="", transaction=None):
    """Creates a page with a list of persons matching the given criterias."""
    req.session['person_lastsearch'] = (fullname, firstname, lastname,
                                         accountname, birthdate)
    page = Main(req)
    page.title = _("Search for person(s):")
    page.setFocus("person/list")
    
    # Store given search parameters in search form
    values = {}
    values['fullname'] = fullname
    values['firstname'] = firstname
    values['lastname'] = lastname
    values['accountname'] = accountname
    values['birthdate'] = birthdate
    form = PersonSearchTemplate(searchList=[{'formvalues': values}])
    
    if fullname or firstname or lastname or accountname or birthdate:
        server = transaction
        
        personsearcher = server.get_person_searcher()
        intersections = []

        if fullname:
            searcher = server.get_person_name_searcher()
            searcher.set_name_variant(server.get_name_type("FULL"))
            searcher.set_name_like(fullname)
            searcher.mark_person()
            intersections.append(searcher)

        if firstname:
            searcher = server.get_person_name_searcher()
            searcher.set_name_variant(server.get_name_type("FIRST"))
            searcher.set_name_like(firstname)
            searcher.mark_person()
            intersections.append(searcher)

        if lastname:
            searcher = server.get_person_name_searcher()
            searcher.set_name_variant(server.get_name_type("LAST"))
            searcher.set_name_like(lastname)
            searcher.mark_person()
            intersections.append(searcher)
        
        if accountname:
            searcher = server.get_account_searcher()
            searcher.set_name_like(accountname)
            searcher.mark_owner()
            intersections.append(searcher)
            
        if birthdate:
            date = server.get_commands().strptime(birthdate, "%Y-%m-%d")
            personsearcher.set_birth_date(date)

        if intersections:
            personsearcher.set_intersections(intersections)
        
        persons = personsearcher.search()
        
        # Print results
        result = html.Division(_class="searchresult")
        header = html.Header(_("Person search results:"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Name"), _("Date of birth"), _("Account(s)"), _("Actions"))
        for person in persons:
            date = person.get_birth_date().strftime("%Y-%m-%d")
            date = html.TableCell(date, align="center")
            accounts = ""
#            for account in person.get_accounts()[:4]:
#                viewaccount = url("account/view?id=%i" % account.get_id())
#                accounts.append(str(html.Anchor(account.get_name(), href=viewaccount)))
#            if len(accounts) > 3:
#                accounts = ", ".join(accounts[:3]) + "..."
#            else:
#                accounts = ", ".join(accounts)
            view = url("person/view?id=%i" % person.get_id())
            edit = url("person/edit?id=%i" % person.get_id())
            link = html.Anchor(_(_primary_name(person)), href=view)
            view = html.Anchor(_('view') , href=view, _class="actions")
            edit = html.Anchor(_('edit') , href=edit, _class="actions")
            table.add(link, date, accounts, str(view)+str(edit))
    
        if persons:
            result.append(table)
        else:
            error = "Sorry, no person(s) found matching the given criteria!"
            result.append(html.Division(_(error), _class="searcherror"))

        result = html.Division(result)
        header = html.Header(_("Search for other person(s):"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        result.append(form.form())
        page.content = result.output
        
    else:
        page.content = form.form
    
    return page

def _primary_name(person):
    """Returns the primary display name for the person."""
    #until such an thing is set in the database, we just use this method.
    names = {}
    for name in person.get_names():
        names[name.get_name_variant().get_name()] = name.get_name()
    for type in ["FULL", "LAST", "FIRST"]:
        if names.has_key(type):
            return names[type]
    return "unknown name"

def _get_person(req, transaction, id):
    """Returns a Person-object from the database with the specific id."""
    try:
        return transaction.get_person(int(id))
    except Exception, e:
        queue_message(req, _("Could not load person with id=%s") % id,
                      error=True)
        queue_message(req, str(e), error=True)
        redirect(req, url("person"), temporary=True)

@transaction_decorator
def view(req, transaction, id, addName=False):
    """Creates a page with a view of the person given by id.

    If addName is True or "True", the form for adding a name is shown.
    """
    person = _get_person(req, transaction, id)
    page = Main(req)
    page.title = _("Person %s:" % _primary_name(person))
    page.setFocus("person/view", str(person.get_id()))
    view = PersonViewTemplate()
    content = view.viewPerson(req, person, addName)
    page.content = lambda: content
    return page

@transaction_decorator
def edit(req, transaction, id, addName=False):
    """Creates a page with the form for editing a person.
    
    If addName is True or "True", the form for adding a name is shown.
    """
    person = _get_person(req, transaction, id)
    page = Main(req)
    page.title = _("Edit %s:" % _primary_name(person))
    page.setFocus("person/edit", str(person.get_id()))
    edit = PersonEditTemplate()
    content = edit.editPerson(req, person, addName)
    page.content = lambda: content
    return page

def create(req, birthnr="", gender="", birthdate="", ou="", affiliation="", aff_status=""):
    """Creates a page with the form for creating a person."""
    page = Main(req)
    page.title = _("Create a new person:")
    page.setFocus("person/create")
    # Store given create parameters in create-form
    values = {}
    values['birthnr'] = birthnr
    values['birthdate'] = birthdate
    values['ou'] = ou
    values['affiliation'] = affiliation
    values['aff_status'] = aff_status
    create = PersonCreateTemplate(searchList=[{'formvalues': values}])
    content = create.form(req)
    page.content = lambda: content
    return page

@transaction_decorator
def save(req, transaction, id, gender, birthdate, description, deceased, save):
    """Store the form for editing a person into the database."""
    person = _get_person(req, transaction, id)
    
    if deceased == "True":
        deceased = True
    else:
        deceased = False
    
    person.set_gender(transaction.get_gender_type(gender))
    person.set_birth_date(transaction.get_commands().strptime(birthdate, "%Y-%m-%d"))
    person.set_description(description)
    person.set_deceased(deceased)
    
    queue_message(req, _("Person successfully updated."))
    redirect_object(req, person, seeOther=True)

    transaction.commit()

@transaction_decorator
def make(req, transaction, name, gender, birthdate, description="Created with cereweb"):
    """Create a new person with the given values."""
    birthdate = transaction.get_commands().strptime(birthdate, "%Y-%m-%d")
    gender = transaction.get_gender_type(gender)
    person = transaction.get_commands().create_person(birthdate, gender)
    
    name_type = transaction.get_name_type('FULL')
    source_system = transaction.get_source_system('Manual')
    person.add_name(name, name_type, source_system)

    if description:
        person.set_description(description)
    
    queue_message(req, _("Person successfully created."))
    redirect_object(req, person, seeOther=True)
    transaction.commit()

@transaction_decorator
def delete(req, transaction, id):
    """Delete the person from the server."""
    person = _get_person(req, transaction, id)
    person.delete()

    queue_message(req, "Person successfully deleted.")
    redirect(req, url("person"), seeOther=True)
    
    transaction.commit()

@transaction_decorator
def add_name(req, transaction, id, name, name_type):
    """Add a new name to the person with the given id."""
    person = _get_person(req, transaction, id)

    name_type = transaction.get_name_type(name_type)
    source_system = transaction.get_source_system('Manual')
    person.add_name(name, name_type, source_system)

    queue_message(req, _("Name successfully added.."))
    redirect_object(req, person, seeOther=True)

    transaction.commit()

# remove_name ser ikke ut til å være støttet av cerebrum-core
def remove_name(req, id, name, variant, ss):
    """Remove the name with the given values."""
    server = req.session.get("active")
    person = _get_person(req, id)

    searcher = server.get_person_name_searcher()
    searcher.set_person(person)
    searcher.set_name_variant(server.get_name_type(variant))
    searcher.set_source_system(server.get_source_system(ss))
    searcher.set_name_like(name)
    name, = searcher.search()

    person.remove_name(name)

    queue_message(req, _("Name successfully removed."))
    redirect_object(req, person, seeOther=True)

@transaction_decorator
def remember(req, transaction, id):
    person = _get_person(req, transaction, int(id))
    obj = ('person', _primary_name(person), id)
    req.session['remembered'].append(obj)
    redirect_object(req, person)
 
# arch-tag: bef096b9-0d9d-4708-a620-32f0dbf42fe6
