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

from Cerebrum.Database import IntegrityError
from Cerebrum.Errors import NotFoundError
from gettext import gettext as _
from mx import DateTime
from lib.utils import strftime, unlegal_name
from lib.utils import queue_message, redirect
from lib.utils import randpasswd
from lib.utils import spine_to_web, web_to_spine
from lib.utils import from_spine_decode, session_required_decorator
from lib.utils import get_database, parse_date, redirect_entity
from lib.data.DTO import DTO
from lib.data.EntityFactory import EntityFactory
from lib.data.PersonDAO import PersonDAO
from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.OuDAO import OuDAO
from lib.data.EmailTargetDAO import EmailTargetDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.PersonSearcher import PersonSearcher
from lib.forms import PersonCreateForm, PersonEditForm
from lib.templates.PersonViewTemplate import PersonViewTemplate

@session_required_decorator
def search(**kwargs):
    """Search after hosts and displays result and/or searchform."""
    searcher = PersonSearcher(**kwargs)
    return searcher.respond()
search.exposed = True
index = search

@session_required_decorator
def view(id, **kwargs):
    """Creates a page with a view of the person given by id."""
    db = get_database()

    page = PersonViewTemplate()
    page.viewBirthNo = kwargs.get('birthno') and True or False
    page.person = PersonDAO(db).get(id, include_extra=True)
    page.person.accounts = PersonDAO(db).get_accounts(id)
    page.person.history = HistoryDAO(db).get_entity_history_tail(id)
    page.affiliation_types = ConstantsDAO(db).get_affiliation_statuses()
    page.ou_tree = OuDAO(db).get_tree("Kjernen")
    page.id_types = ConstantsDAO(db).get_id_types()
    page.name_types = ConstantsDAO(db).get_name_types()
    page.quarantines = ConstantsDAO(db).get_quarantines()
    return page.respond()
view.exposed = True

@session_required_decorator
def edit(id, **kwargs):
    """Creates a page with the form for editing a person."""
    form = PersonEditForm(id, **kwargs)
    if form.is_correct():
        return save(**form.get_values())
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(**kwargs):
    """Creates a page with the form for creating a person."""
    form = PersonCreateForm(**kwargs)
    if form.is_correct():
        try:
            return make(**form.get_values())
        except ValueError, e:
            message = spine_to_web(_(e.message))
        except IntegrityError, e:
            message = _("The person can not be created because it violates the integrity of the database.  Try changing the NIN.")
        queue_message(message, error=True, title=_("Create failed"))
    return form.respond()
create.exposed = True

def make(ou, status, firstname, lastname, externalid, gender, birthdate, description):
    """Create a new person with the given values."""
    db = get_database()
    dao = PersonDAO(db)
    person = DTO()
    populate(person, gender, birthdate, None, description)
    populate_name(person, firstname, lastname)

    dao.create(person)
    dao.add_affiliation_status(person.id, ou, status)

    if externalid:
        dao.add_birth_no(person.id, externalid)

    db.commit()

    queue_message(_("Person successfully created.  Now he probably needs an account."), title="Person created")
    redirect('/account/create?owner_id=%s' % person.id)

def populate_name(person, firstname, lastname):
    person.first_name = web_to_spine(firstname)
    person.last_name = web_to_spine(lastname)

def save(id, gender, birthdate, deceased, description):
    db = get_database()
    dao = PersonDAO(db)
    dto = dao.get(id)
    dto.gender = DTO()
    dto.gender.id = gender
    dto.birth_date = parse_date(birth_date)
    dto.description = description and web_to_spine(description.strip())
    dto.deceased_date = parse_date(deceased)
    dao.save(dto)
    db.commit()

    msg = _("Person successfully updated.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(dto)

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
    member = EntityFactory(db).get_entity(member_id)

    dao = GroupDAO(db)
    dao.remove_member(group_id, member_id)
    db.commit()

    return _("Removed %s from group %s") % (member.name, group.name)

def get_primary_account(owner_id):
    db = get_database()
    accounts = PersonDAO(db).get_accounts(owner_id)
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
    db = get_database()
    targets = EmailTargetDAO(db).get_from_entity(account.id)
    for target in targets:
        return target.primary.address
    return ""

def get_affiliation(person):
    affiliations = (x for x in person.affiliations if not x.is_deleted)
    for aff in affiliations:
        return aff
    return None

def get_faculty(ou):
    db = get_database()
    faculty = OuDAO(db).get_parent(ou.id, 'Kjernen')
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

    db = get_database()
    person = PersonDAO(db).get(id, include_extra=True)
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
