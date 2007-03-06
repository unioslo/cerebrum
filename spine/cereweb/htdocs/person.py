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
import re
import string

from gettext import gettext as _
from lib.Main import Main
from lib.utils import strftime, strptime, commit_url
from lib.utils import queue_message, redirect, redirect_object
from lib.utils import transaction_decorator, object_link, commit
from lib.utils import legal_date, rollback_url
from lib.templates.FormWidgets import FormWidgets
from lib.WorkList import remember_link
from lib.Searchers import PersonSearcher
from lib.Forms import PersonCreateForm
from lib.templates.SearchResultTemplate import SearchResultTemplate
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.FormTemplate import FormTemplate
from lib.templates.PersonViewTemplate import PersonViewTemplate
from lib.templates.PersonEditTemplate import PersonEditTemplate
from lib.templates.PersonCreateTemplate import PersonCreateTemplate

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Person")
    page.setFocus("person/search")
    page.search_title = _('A person')
    page.search_fields = [("name", _("Name")),
                          ("accountname", _("Account name")),
                          ("birthdate", _("Date of birth *")),
                          ("spread", _("Spread name")),
                          ("ou", _("Affiliated to Organizational Unit")),
                          ("aff", _("Affiliation Type"))
                        ]
    page.search_help = [_("* Date of birth: (YYYY-MM-DD), exact match"),
                        _("A person may have several types of names, and therefor a search for a name will be testet on all the nametypes.")]
    page.search_action = '/person/search'
    page.form_values = remembered
    return page.respond()

def search(transaction, **vargs):
    """Search after hosts and displays result and/or searchform."""
    args = ( 'name', 'accountname', 'birthdate', 'spread', 'ou', 'aff')
    searcher = PersonSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = transaction_decorator(search)
search.exposed = True
index = search

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

def _get_person(transaction, id):
    """Returns a Person-object from the database with the specific id."""
    try:
        return transaction.get_person(int(id))
    except Exception, e:
        queue_message(_("Could not find person with id=%s") % id, True)
        redirect('index')

def view(transaction, id, **vargs):
    """Creates a page with a view of the person given by id."""
    person = transaction.get_person(int(id))
    page = Main()
    page.title = _("Person %s" % _primary_name(person))
    page.setFocus("person/view", id)
    content = PersonViewTemplate().view(transaction, person)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a person."""
    person = transaction.get_person(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(person)
    page.setFocus("person/edit", id)

    genders = [(g.get_name(), g.get_description()) for g in 
               transaction.get_gender_type_searcher().search()]

    edit = PersonEditTemplate()
    content = edit.editPerson(person, genders)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def create(transaction, **vargs):
    """Creates a page with the form for creating a person."""
    form = PersonCreateForm(transaction, **vargs)
    if not vargs:
        return create_form(transaction, **vargs)
    elif not form.has_required() or not form.is_correct():
        return create_form(transaction, message=form.get_error_message(), **vargs)
    else:
        make(transaction,
            vargs['firstname'],
            vargs['lastname'],
            vargs['gender'],
            vargs['birthdate'],
            vargs['externalid'],
            vargs['description'])
create = transaction_decorator(create)
create.exposed = True

def make(transaction, firstname, lastname, gender, birthdate, externalid, description=""):
    """Create a new person with the given values."""
    birthdate = strptime(transaction, birthdate)
    gender = transaction.get_gender_type(gender)
    source_system = transaction.get_source_system('Manual')
    person = transaction.get_commands().create_person(
           birthdate, gender, firstname, lastname, source_system)
    if description:
        person.set_description(description)
    commit(transaction, person, msg=_("Person successfully created."))

def create_form(transaction, message=None, **values):
    """Creates a page with the form for creating a person."""
    page = FormTemplate()
    if message:
        page.messages.append(message)
    page.title = _("Person")
    page.form_title = _("Create new person")
    page.form_action = "/person/create"

    genders = [(g.get_name(), g.get_description()) for g in 
               transaction.get_gender_type_searcher().search()]
    values['gender_options'] = genders
    form = PersonCreateForm(transaction, **values)
    page.form_fields = form.get_fields()

    return page.respond()

def save(transaction, id, gender, birthdate,
         deceased="", description="", submit=None):
    """Store the form for editing a person into the database."""
    person = transaction.get_person(int(id))

    if submit == "Cancel":
        redirect_object(person)
        return
    
    person.set_gender(transaction.get_gender_type(gender))
    person.set_birth_date(strptime(transaction, birthdate))
    person.set_description(description)
    person.set_deceased_date(strptime(transaction, deceased))
    
    commit(transaction, person, msg=_("Person successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def delete(transaction, id):
    """Delete the person from the server."""
    person = transaction.get_person(int(id))
    msg = _("Person '%s' successfully deleted.") % _primary_name(person)
    person.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def add_name(transaction, id, name, name_type):
    """Add a new name to the person with the given id."""
    person = transaction.get_person(int(id))

    name_type = transaction.get_name_type(name_type)
    source_system = transaction.get_source_system('Manual')
    person.set_name(name, name_type, source_system)

    commit(transaction, person, msg=_("Name successfully added."))
add_name = transaction_decorator(add_name)
add_name.exposed = True

def remove_name(id, transaction, variant, ss):
    """Remove the name with the given values."""
    person = transaction.get_person(int(id))
    variant = transaction.get_name_type(variant)
    ss = transaction.get_source_system(ss)

    person.remove_name(variant, ss)

    commit(transaction, person, msg=_("Name successfully removed."))
remove_name = transaction_decorator(remove_name)
remove_name.exposed = True

def accounts(owner, transaction, add=None, delete=None, **checkboxes):
    if add:
        redirect('/account/create?owner=%s' % owner)

    elif delete:
        person = _get_person(transaction, owner)
        operation = transaction.get_group_member_operation_type("union")
        msgs = []
        for arg, value in checkboxes.items():
            if arg.startswith("account_"):
                id = arg.replace("account_", "")
                account = transaction.get_account(int(id))
                date = transaction.get_commands().get_date_now()
                account.set_expire_date(date)
                msgs.append(_("Expired account %s.") % account.get_name())
            elif arg.startswith("member_"):
                member_id, group_id = arg.split("_")[1:3]
                member = transaction.get_account(int(member_id))
                group = transaction.get_group(int(group_id))
                group_member = transaction.get_group_member(group, 
                            operation, member, member.get_type())
                group.remove_member(group_member)
                msgs.append(_("Removed %s from group %s") % 
                            (member.get_name(), group.get_name()))
        if msgs:
            olink = object_link(person)
            for msg in msgs:
                queue_message(msg, error=False, link=olink)
            commit(transaction, person)
        else:
            msg = _("No changes done since no groups/accounts were selected.")
            queue_message(msg, error=True)
            redirect_object(person)
        
    else:
        raise "I don't know what you want to do"
accounts = transaction_decorator(accounts)
accounts.exposed = True
                
def add_affil(transaction, id, status, ou, description=""):
    person = transaction.get_person(int(id))
    ou = transaction.get_ou(int(ou))
    status = transaction.get_person_affiliation_status(int(status))
    ss = transaction.get_source_system("Manual")

    affil = person.add_affiliation(ou, status, ss)
    
    if description:
        affil.set_description(description)
    
    commit(transaction, person, msg=_("Affiliation successfully added."))
add_affil = transaction_decorator(add_affil)
add_affil.exposed = True

def remove_affil(transaction, id, ou, affil, ss):
    person = transaction.get_person(int(id))
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
    
    commit(transaction, person, msg=_("Affiliation successfully removed."))
remove_affil = transaction_decorator(remove_affil)
remove_affil.exposed = True

# arch-tag: bef096b9-0d9d-4708-a620-32f0dbf42fe6
