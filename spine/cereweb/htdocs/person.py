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

import SpineIDL
from Cerebrum.Database import IntegrityError
from Cerebrum.Errors import NotFoundError
from account import _get_links
from gettext import gettext as _
from mx import DateTime
from lib.Main import Main
from lib.utils import strftime, strptime, commit_url, unlegal_name
from lib.utils import queue_message, redirect, redirect_object
from lib.utils import transaction_decorator, object_link, commit
from lib.utils import legal_date, rollback_url, html_quote, randpasswd
from lib.utils import spine_to_web, web_to_spine, get_lastname_firstname
from lib.utils import from_spine_decode, session_required_decorator
from lib.utils import get_database, parse_date, redirect_entity, entity_link
from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.PersonDAO import PersonDAO
from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.OuDAO import OuDAO
from lib.data.HostDAO import HostDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.Searchers import PersonSearcher
from lib.Forms import PersonCreateForm, PersonEditForm
from lib.templates.SearchResultTemplate import SearchResultTemplate
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.FormTemplate import FormTemplate
from lib.templates.PersonViewTemplate import PersonViewTemplate

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Person")
    page.set_focus("person/search")
    page.links = _get_links()
    page.search_title = _('A person')
    page.search_fields = [("name", _("Name")),
                          ("accountname", _("Account name")),
                          ("birthdate", _("Date of birth *")),
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

@session_required_decorator
def view(id, **vargs):
    """Creates a page with a view of the person given by id."""
    page = PersonViewTemplate()
    page.person = PersonDAO().get(id, include_extra=True)
    page.person.accounts = PersonDAO().get_accounts(id)
    page.person.history = HistoryDAO().get_entity_history_tail(id)
    page.affiliation_types = ConstantsDAO().get_affiliation_statuses()
    page.ou_tree = OuDAO().get_tree("Kjernen")
    page.id_types = ConstantsDAO().get_id_types()
    page.name_types = ConstantsDAO().get_name_types()
    page.viewBirthNo = vargs.get('birthno') and True or False
    return page.respond()
view.exposed = True

def edit_form(form, message=None):
    page = FormTemplate()
    if message:
        page.messages.append(message)
    page.title = form.get_title()
    page.form_title = form.get_title()
    page.set_focus("person/edit")
    page.links = _get_links()
    page.form_fields = form.get_fields()
    page.form_action = "/person/edit"
    return page.respond()

@session_required_decorator
def edit(id, **vargs):
    """Creates a page with the form for editing a person."""
    person = PersonDAO().get(id)
    get_date = lambda x: x and strftime(x, '%Y-%m-%d') or ''
    values = {
        'id': id,
        'gender': person.gender.name,
        'birthdate': get_date(person.birth_date),
        'description': person.description,
        'deceased': get_date(person.deceased_date),
    }
    values.update(vargs)

    form = PersonEditForm(None, **values)
    form.title = entity_link(person)

    if not vargs:
        return edit_form(form)
    if not form.has_required() or not form.is_correct():
        return edit_form(form, message=form.get_error_message())
    else:
        vargs = form.get_values()
        save(**vargs)
edit.exposed = True

@session_required_decorator
def create(**vargs):
    """Creates a page with the form for creating a person."""
    form = PersonCreateForm(None, **vargs)

    if not vargs:
        return create_form(form)

    if not form.has_required() or not form.is_correct():
        return create_form(form, message=form.get_error_message())

    birth_no = vargs.get('externalid', '').strip()
    desc = vargs.get('description', '').strip()

    if not birth_no and not desc:
        msg = 'If NIN is empty the reason must be specified in description.'
        return create_form(form, message=msg)
    elif not birth_no:
        username = cherrypy.session.get('username')
        create_date = DateTime.now().strftime("%Y-%m-%d")
        desc = 'Registered by: %s on %s\n' % (username, create_date) + desc

    try:
        make(
            vargs.get('ou'),
            vargs.get('status'),
            vargs.get('firstname'),
            vargs.get('lastname'),
            vargs.get('gender'),
            vargs.get('birthdate'),
            birth_no,
            desc)
    except ValueError, e:
        message = (spine_to_web(e.message), True)
    except IntegrityError, e:
        message = ("The person can not be created because it violates the integrity of the database.  Try changing the NIN.",  True)
    return create_form(form, message)
create.exposed = True

def make(ou, status, firstname, lastname, gender, birthdate, birth_no, description):
    """Create a new person with the given values."""
    db = get_database()
    dao = PersonDAO(db)
    person = DTO()
    populate(person, gender, birthdate, None, description)
    populate_name(person, firstname, lastname)

    dao.create(person)
    dao.add_affiliation_status(person.id, ou, status)

    if birth_no:
        dao.add_birth_no(person.id, birth_no)

    db.commit()

    queue_message(_("Person successfully created.  Now he probably needs an account."), title="Person created")
    redirect('/account/create?owner_id=%s' % person.id)

def populate_name(person, firstname, lastname):
    person.first_name = web_to_spine(firstname)
    person.last_name = web_to_spine(lastname)

def create_form(form, message=None):
    """Creates a page with the form for creating a person."""
    page = FormTemplate()
    if message:
        page.messages.append(message)
    page.title = _("Person")
    page.set_focus("person/create")
    page.links = _get_links()
    page.form_title = _("Create new person")
    page.form_action = "/person/create"
    page.form_fields = form.get_fields()

    return page.respond()

def save(id, gender, birthdate, deceased='', description=''):
    """Store the form for editing a person into the database."""
    db = get_database()
    dao = PersonDAO(db)
    dto = dao.get(id)
    populate(dto, gender, birthdate, deceased, description)
    dao.save(dto)
    db.commit()

    msg = _("Person successfully updated.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(dto)

def populate(dto, gender, birth_date, deceased, description):
    dto.gender = DTO()
    dto.gender.id = gender
    dto.birth_date = parse_date(birth_date)
    dto.description = description and web_to_spine(description.strip())
    dto.deceased_date = parse_date(deceased)

@session_required_decorator
def delete(id):
    """Delete the person from the server."""
    db = get_database()
    dao = PersonDAO(db)
    person = dao.delete(id)
    db.commit()

    msg = _("Person '%s' successfully deleted.") % spine_to_web(person.name)
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect('index')
delete.exposed = True

@session_required_decorator
def add_name(id, name, name_type):
    """Add a new name to the person with the given id."""
    msg = unlegal_name(name)
    if msg:
        queue_message(msg, error=True)
        redirect_entity(id)

    db = get_database()
    dao = PersonDAO(db)
    dao.add_name(id, web_to_spine(name_type), web_to_spine(name.strip()))
    db.commit()

    msg = _("Name successfully added.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(id)
add_name.exposed = True

@session_required_decorator
def remove_name(id, variant, ss):
    """Remove the name with the given values."""
    db = get_database()
    dao = PersonDAO(db)
    dao.remove_name(id, int(variant), int(ss))
    db.commit()

    msg=_("Name successfully removed.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(id)
remove_name.exposed = True

@session_required_decorator
def add_affil(id, status, ou, description=""):
    db = get_database()
    dao = PersonDAO(db)
    dao.add_affiliation_status(id, ou, status)
    db.commit()

    msg = _("Affiliation successfully added.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(id)
add_affil.exposed = True

@session_required_decorator
def remove_affil(id, ou, affil, ss):
    db = get_database()
    dao = PersonDAO(db)
    dao.remove_affiliation_status(id, ou, affil, ss)
    db.commit()

    msg = _("Affiliation successfully removed.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(id)
remove_affil.exposed = True

@session_required_decorator
def accounts(owner_id, **checkboxes):
    msgs = []
    for arg, value in checkboxes.items():
        if arg.startswith("account_"):
            msg = expire_account(arg)
        elif arg.startswith("member_"):
            msg = leave_group(arg)
        else:
            continue

        msgs.append(msg)

    if not msgs:
        msgs.append(_("No changes done since no groups/accounts were selected."))

    for msg in msgs:
        queue_message(msg, title="Success", error=False)
    redirect_entity(owner_id)
accounts.exposed = True

def expire_account(arg):
    id = arg.replace("account_", "")
    db = get_database()
    dao = AccountDAO(db)
    account = dao.get(id)
    account.expire_date = DateTime.now()
    dao.save(account)
    db.commit()

    return _("Expired account %s.") % account.name

def leave_group(arg):
    member_id, group_id = arg.split("_")[1:3]
    member_id = int(member_id)
    group_id = int(group_id)

    db = get_database()
    group = GroupDAO(db).get_entity(group_id)
    member = EntityDAO(db).get(member_id)

    dao = GroupDAO(db)
    dao.remove_member(group_id, member_id)
    db.commit()

    return _("Removed %s from group %s") % (member.name, group.name)

def get_primary_account(owner_id):
    accounts = PersonDAO().get_accounts(owner_id)
    if not accounts:
        raise NotFoundError("primary account")

    prim_account = [x for x in accounts if x.is_primary]
    if not prim_account:
        prim_account = accounts
    return prim_account[0]

def get_names(person):
    lastname = None
    firstname = None
    for name in person.names:
        source_systems = [x.name for x in name.source_systems]
        if 'Cached' in source_systems:
            if name.variant.name == 'LAST':
                lastname = from_spine_decode(name.value)
            if name.variant.name == 'FIRST':
                firstname = from_spine_decode(name.value)
    return firstname, lastname

def get_email_address(account):
    targets = HostDAO().get_email_targets(account.id)
    for target in targets:
        return target.address
    return ""

def get_affiliation(person):
    affiliations = (x for x in person.affiliations if not x.is_deleted)
    for aff in affiliations:
        return aff
    return None

def get_faculty(ou):
    faculty = OuDAO().get_parent(ou.id, 'Kjernen')
    return faculty and from_spine_decode(faculty.name) or ""

def change_password(account):
    new_password = randpasswd()
    db = get_database()
    dao = AccountDAO(db)
    dao.set_password(account.id, new_password)
    db.commit()
    return new_password

@session_required_decorator
def print_contract(id, lang):
    from lib.CerebrumUserSchema import CerebrumUserSchema
    referer = cherrypy.request.headerMap.get('Referer', '')
    try:
        prim_account = get_primary_account(id)
    except NotFoundError, e:
        msg = _("The person must have an account.")
        queue_message(msg, title="Could not print contract", error=True)
        redirect_entity(id)

    person = PersonDAO().get(id, include_extra=True)
    username = from_spine_decode(prim_account.name)
    firstname, lastname = get_names(person)
    email_address = get_email_address(prim_account)

    passwd = change_password(prim_account)
    studyprogram = None
    year = None
    birthdate = person.birth_date.strftime('%d-%m-%Y')
    affiliation = get_affiliation(person)
    if not affiliation:
        msg = _('The person has no affiliation.')
        queue_message(msg, title="Could not print contract", error=True)
        redirect_entity(id)

    faculty = get_faculty(affiliation.ou)
    department = from_spine_decode(affiliation.ou.name)

    pdfSchema= CerebrumUserSchema(lastname, firstname, email_address, username, passwd, birthdate, studyprogram, year, faculty, department, lang)
    pdfContent = pdfSchema.build()
    if pdfContent:
        contentLength = len(pdfContent)
        cherrypy.response.headers['Content-Type'] = 'application/pdf'
        cherrypy.response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate, max-age=0'
        cherrypy.response.headers['pragma'] = 'no-cache'
        cherrypy.response.headers['Content-Disposition'] = 'inline; filename='+username+'-contract.pdf'
        cherrypy.response.headers['Content-Transfer-Encoding'] = 'binary'
        cherrypy.response.headers['Content-Length'] = str(contentLength)
        ## outFile = open("/tmp/contract.pdf", "w")
        ## outFile.write(pdfContent)
        ## outFile.close()
        return pdfContent
    else:
        msg = _('Could not generate pdf.')
        queue_message(msg, title="Could not print contract", error=True)
        redirect_entity(id)
print_contract.exposed = True
