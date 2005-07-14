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
    return search(req, *req.session.get('person_lastsearch', ()))

def search(req, name="", accountname="", birthdate="", spread="", transaction=None):
    """Creates a page with a list of persons matching the given criterias."""
    req.session['person_lastsearch'] = (name, accountname, birthdate, spread)
    page = Main(req)
    page.title = _("Search for person(s):")
    page.setFocus("person/list")
    
    # Store given search parameters in search form
    values = {}
    values['name'] = name
    values['accountname'] = accountname
    values['birthdate'] = birthdate
    values['spread'] = spread
    form = PersonSearchTemplate(searchList=[{'formvalues': values}])
    
    if name or accountname or birthdate or spread:
        """
        Searches first through accountnames and birthdates,
        then perform an intersection with the result of a search
        through all name_types for 'name'.
        """
        personsearcher = transaction.get_person_searcher()
        intersections = []

        if accountname:
            searcher = transaction.get_account_searcher()
            searcher.set_name_like(accountname)
            searcher.mark_owner()
            intersections.append(searcher)
            
        if birthdate:
            date = transaction.get_commands().strptime(birthdate, "%Y-%m-%d")
            personsearcher.set_birth_date(date)

        if name:
            searcher = transaction.get_person_name_searcher()
            searcher.set_name_like(name)
            searcher.mark_person()
            intersections.append(searcher)


        if spread:
            persons = sets.Set()
            spreadsearcher = transaction.get_spread_searcher()
            spreadsearcher.set_name_like(spread)
            for spread in spreadsearcher.search():
                searcher = transaction.get_entity_spread_searcher()
                searcher.set_spread(spread)
                searcher.mark_entity()
                personsearcher.set_intersections(intersections + [searcher])

                persons.update(personsearcher.search())

        else:
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
            accounts = [str(object_link(i)) for i in person.get_accounts()[:4]]
            accounts = ', '.join(accounts[:3]) + (len(accounts) == 4 and '...' or '')

            view = str(object_link(person, text="view", _class="actions"))
            edit = str(object_link(person, text="edit", method="edit", _class="actions"))
            remb = str(remember_link(person, _class="actions"))
            table.add(object_link(person), date, accounts, view+edit+remb)
    
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
search = transaction_decorator(search)

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

def view(req, transaction, id, addName=False, addAffil=False):
    """Creates a page with a view of the person given by id.

    If addName is True or "True", the form for adding a name is shown.
    If addAffil is True or "True", the form for adding an affiliation is shown.
    """
    person = _get_person(req, transaction, id)
    page = Main(req)
    page.title = _("Person %s:" % _primary_name(person))
    page.setFocus("person/view", str(person.get_id()))
    view = PersonViewTemplate()
    content = view.viewPerson(transaction, person, addName, addAffil)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    """Creates a page with the form for editing a person."""
    person = _get_person(req, transaction, id)
    page = Main(req)
    page.title = _("Edit %s:" % _primary_name(person))
    page.setFocus("person/edit", str(person.get_id()))

    genders = [(g.get_name(), g.get_description()) for g in 
               transaction.get_gender_type_searcher().search()]

    edit = PersonEditTemplate()
    content = edit.editPerson(person, genders)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def create(req, transaction, name="", gender="", birthdate="", description=""):
    """Creates a page with the form for creating a person."""
    page = Main(req)
    page.title = _("Create a new person:")
    page.setFocus("person/create")

    genders = [(g.get_name(), g.get_description()) for g in 
               transaction.get_gender_type_searcher().search()]
    
    # Store given create parameters in create-form
    values = {}
    values['name'] = name
    values['birthdate'] = birthdate
    values['gender'] = gender
    values['description'] = description

    genders = [(g.get_name(), g.get_description()) for g in 
               transaction.get_gender_type_searcher().search()]
    
    create = PersonCreateTemplate(searchList=[{'formvalues': values}])
    content = create.form(genders)
    page.content = lambda: content
    return page
create = transaction_decorator(create)

def save(req, transaction, id, gender, birthdate, deceased, description=""):
    """Store the form for editing a person into the database."""
    person = _get_person(req, transaction, id)
    
    if deceased == "True":
        deceased = True
    else:
        deceased = False
    
    person.set_gender(transaction.get_gender_type(gender))
    person.set_birth_date(transaction.get_commands().strptime(birthdate, "%Y-%m-%d"))
    person.set_description(description)
    a=person.get_deceased()
    person.set_deceased(deceased)
    
    b=person.get_deceased()
    
    redirect_object(req, person, seeOther=True)
    transaction.commit()
    queue_message(req, _("Person successfully updated. %s, %s, %s" % (a,b,deceased)))
save = transaction_decorator(save)

def make(req, transaction, name, gender, birthdate, description=""):
    """Create a new person with the given values."""
    birthdate = transaction.get_commands().strptime(birthdate, "%Y-%m-%d")
    gender = transaction.get_gender_type(gender)
    source_system = transaction.get_source_system('Manual')
    
    person = transaction.get_commands().create_person(
               birthdate, gender, name, source_system)

    if description:
        person.set_description(description)
    
    redirect_object(req, person, seeOther=True)
    transaction.commit()
    queue_message(req, _("Person successfully created."))
make = transaction_decorator(make)

def delete(req, transaction, id):
    """Delete the person from the server."""
    person = _get_person(req, transaction, id)
    person.delete()

    redirect(req, url("person"), seeOther=True)
    transaction.commit()
    queue_message(req, "Person successfully deleted.")
delete = transaction_decorator(delete)

def add_name(req, transaction, id, name, name_type):
    """Add a new name to the person with the given id."""
    person = _get_person(req, transaction, id)

    name_type = transaction.get_name_type(name_type)
    source_system = transaction.get_source_system('Manual')
    person.set_name(name, name_type, source_system)

    redirect_object(req, person, seeOther=True)
    transaction.commit()
    queue_message(req, _("Name successfully added."))
add_name = transaction_decorator(add_name)

def remove_name(req, id, transaction, variant, ss):
    """Remove the name with the given values."""
    person = _get_person(req, transaction, id)
    variant = transaction.get_name_type(variant)
    ss = transaction.get_source_system(ss)

    person.remove_name(variant, ss)

    redirect_object(req, person, seeOther=True)
    transaction.commit()
    queue_message(req, _("Name successfully removed."))
remove_name = transaction_decorator(remove_name)

def accounts(req, owner, transaction, add=None, delete=None, **checkboxes):
    if add:
        redirect(req, url('account/create?owner=%s' % owner))

    elif delete:
        operation = transaction.get_group_member_operation_type("union")
        for arg, value in checkboxes.items():
            if arg.startswith("account_"):
                id = arg.replace("account_", "")
                account = transaction.get_account(int(id))
                date = transaction.get_commands().get_date_now()
                account.set_expire_date(date)
                queue_message(req, _("Expired account %s.") % account.get_name())
            elif arg.startswith("member_"):
                member_id, group_id = arg.split("_")[1:3]
                member = transaction.get_account(int(member_id))
                group = transaction.get_group(int(group_id))
                group_member = transaction.get_group_member(group, 
                            operation, member, member.get_type())
                group.remove_member(group_member)
                queue_message(req, _("Removed %s from group %s") % 
                        (member.get_name(), group.get_name()))
        person = _get_person(req, transaction, owner)
        redirect_object(req, person, seeOther=True)
        transaction.commit()              
        
    else:
        raise "I don't know what you want to do"
accounts = transaction_decorator(accounts)
                
def add_affil(req, transaction, id, status, ou, description=""):
    person = _get_person(req, transaction, id)
    ou = transaction.get_ou(int(ou))
    status = transaction.get_person_affiliation_status_type(status)
    ss = transaction.get_source_system("Manual")

    affil = person.add_affiliation(ou, status, ss)
    
    if description:
        affil.set_description(description)
    
    redirect_object(req, person, seeOther=True)
    transaction.commit()
    queue_message(req, _("Affiliation successfully added."))
add_affil = transaction_decorator(add_affil)

def remove_affil(req, transaction, id, ou, affil, ss):
    person = _get_person(req, transaction, id)
    ou = transaction.get_ou(int(ou))
    ss = transaction.get_source_system(ss)
    affil = transaction.get_person_affiliation_type(affil)
    
    searcher = transaction.get_person_affiliation_searcher()
    searcher.set_person(person)
    searcher.set_ou(ou)
    searcher.set_source_system(ss)
    searcher.set_affiliation(affil)
    
    affiliation, = searcher.search()
    affiliation.delete()
    
    redirect_object(req, person, seeOther=True)
    transaction.commit()
    queue_message(req, _("Affiliation successfully removed."))
remove_affil = transaction_decorator(remove_affil)

# arch-tag: bef096b9-0d9d-4708-a620-32f0dbf42fe6
