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
from lib.utils import *
from lib.Searchers import AccountSearcher
from lib.Forms import AccountCreateForm
from lib.templates.FormTemplate import FormTemplate
from lib.templates.AccountViewTemplate import AccountViewTemplate
from Cerebrum.modules.PasswordChecker import PasswordGoodEnoughException
from Cerebrum.Errors import NotFoundError
from Cerebrum.Database import IntegrityError

from lib.data.AccountDAO import AccountDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DiskDAO import DiskDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.HostDAO import HostDAO
from lib.data.PersonDAO import PersonDAO
from lib.data.DTO import DTO

from lib.utils import get_database

class CreationFailedError(Exception):
    def __init__(self, message, innerException=None):
        self.message = message
        self.innerException = innerException

def _get_links():
    return (
        ('search', _('Search')),
        ('create', _('Create')),
    )

def search(transaction, **vargs):
    """Search for accounts and display results and/or searchform.""" 
    args = ('name', 'spread', 'create_date', 'expire_date', 'description')
    searcher = AccountSearcher(transaction, *args, **vargs)
    return searcher.respond() or view_form(searcher.get_form())
search = transaction_decorator(search)
search.exposed = True
index = search

def view_form(form, message=None):
    page = FormTemplate()
    if message:
        page.messages.append(message)
    page.title = _("Account")
    page.set_focus("account/")
    page.links = _get_links()
    page.form_title = form.get_title()
    page.form_action = form.get_action()
    page.form_fields = form.get_fields()
    page.form_help = form.get_help()
    return page.respond()
    
@session_required_decorator
def create(**kwargs):
    owner_id = kwargs.get('owner_id', None)
    if owner_id is None:
        return fail_to_referer(_("Please create an account through a person or group."))

    try:
        owner = EntityDAO().get(owner_id)
    except NotFoundError, e:
        return fail_to_referer(_("Please create an account through a person or group."))

    if owner.type_name not in ('person', 'group'):
        return fail_to_referer(_("Please create an account through a person or group."))

    form = AccountCreateForm(None, owner_entity=owner, **kwargs)
    if len(kwargs.keys()) == 1:
        return view_form(form)
    elif not form.is_correct():
        return view_form(form, form.get_error_message())
        
    try:
        db = get_database()
        account = make(db, owner, **kwargs)
        db.commit()
    except CreationFailedError, e:
        queue_message(e.message, title=_("Creation failed"), error=True, tracebk=e)
        db.rollback()
        return view_form(form)

    queue_message(_("Account successfully created."), title="Account created")
    redirect_entity(account)
create.exposed = True

def make(db, owner, **kwargs):
    account = create_account(db, owner, **kwargs)
    join_owner_group(db, owner, account)
    join_primary_group(db, account, **kwargs)
    set_account_password(db, account, **kwargs)
    return account

def create_account(db, owner, **kwargs):
    username = web_to_spine(kwargs.get('_other') or kwargs.get('name'))
    expire_date = kwargs.get('expire_date') or None
    
    np_type = None
    if owner.type_name == 'group':
        np_type = kwargs.get('np_type') or None

    account = DTO()
    account.name = username
    account.owner = owner
    account.expire_date = expire_date
    account.np_type = np_type
    try:
        return AccountDAO(db).create(account)
    except IntegrityError, e:
        msg = _("Account creation failed.  Please try a different username.")
        raise CreationFailedError(msg, e)

def join_owner_group(db, owner, account, **kwargs):
    if not owner.type_name == "group":
        return

    join = kwargs.get('join')
    if join:
        dao = GroupDAO(db)
        dao.add_member(account.id, owner.id)

def join_primary_group(db, account, **kwargs):
    primary_group_name = kwargs.get('group')
    
    if not primary_group_name:
        return

    dao = GroupDAO(db)

    try:
        primary_group = dao.get_by_name(primary_group_name)
    except NotFoundError, e:
        msg = _("Account creation failed.  Specified primary group does not exist.")
        raise CreationFailedError(msg, e)

    dao.add_member(account.id, primary_group.id)
        
    if primary_group.is_posix:
        AccountDAO(db).promote_posix(account.id, primary_group.id)

def set_account_password(db, account, **kwargs):
    # We've already verified that password0 == password1.
    password = kwargs.get('password0') or kwargs.get('randpwd')
    
    if not password:
        msg = _('Account creation failed.  Password is empty.')
        raise CreationFailedError(msg, e)

    try:
        dao = AccountDAO(db)
        dao.set_password(account.id, password)
    except PasswordGoodEnoughException, e:
        msg = _('Account creation failed.  Password is not strong enough.')
        raise CreationFailedError(msg, e)

def fail_to_index(message):
    fail('/index', message)

def fail_to_referer(message):
    referer = cherrypy.request.headerMap.get('Referer', '')
    if not referer or referer == cherrypy.request.browser_url:
        fail_to_index(message)
    fail(referer, message)

def fail(url, message):
    queue_message(message, title=_("Operation failed"), error=True)
    redirect(url)

@session_required_decorator
def view(id, **kwargs):
    page = AccountViewTemplate()
    page.account = AccountDAO().get(id, include_extra=True)
    page.account.history = HistoryDAO().get_entity_history_tail(id)
    page.affiliations = PersonDAO().get_affiliations(page.account.owner.id)
    page.shells = ConstantsDAO().get_shells()
    page.disks = DiskDAO().get_disks()
    page.email_target_types = ConstantsDAO().get_email_target_types()
    page.email_servers = HostDAO().get_email_servers()
    page.targets = HostDAO().get_email_targets(id)
    page.spreads = ConstantsDAO().get_user_spreads()

    return page.respond()
view.exposed = True

def save(**kwargs):
    account_id = kwargs.get('id')
    db = get_database()
    dao = AccountDAO(db)
    dto = dao.get(account_id)
    populate(dto, **kwargs)
    populate_posix(dto, **kwargs)
    dao.save(dto)
    db.commit()
    msg = _("Account successfully updated.")
    queue_message(msg, title=_("Operation succeded"), error=False)
    redirect_entity(dto)
save.exposed = True

def populate(dto, expire_date=None, **kwargs):
    dto.expire_date = clean_expire_date(expire_date)

def populate_posix(dto, uid=None, shell=None, gecos=None, group=None, **kwargs):
    if not dto.is_posix: return

    dto.posix_uid = clean_uid(uid)
    dto.shell = clean_shell(shell)
    dto.gecos = clean_gecos(gecos)
    dto.primary_group.id = clean_primary_group(group)

def clean_expire_date(expire_date):
    if not expire_date: return None
    return parse_date(expire_date)

def clean_uid(uid):
    if not uid: return None
    return int(uid)

def clean_shell(shell):
    if not shell: return None
    return web_to_spine(shell)

def clean_gecos(gecos):
    return web_to_spine(gecos)

def clean_primary_group(group):
    if not group: return None
    return int(group)

def get_primary_group_id(account_id):
    posix_groups = AccountDAO().get_posix_groups(account_id)
    for group in posix_groups: return group.id
    return None

def promote_posix(account_id):
    primary_group = get_primary_group_id(account_id)
    if primary_group is None:
        #TODO: maybe we should rather create the posix-group
        msg = "Account is not member of any posix-groups, and cannot be promoted."
        queue_message(_(msg), True, title=_("Promote failed"))
        redirect_entity(account_id)
    else:
        _promote_posix(account_id, primary_group)
        msg = _("Account successfully promoted to posix.")
        queue_message(_(msg), title=_("Promote succeeded"))
        redirect_entity(account_id)
promote_posix.exposed = True

def _promote_posix(account_id, primary_group_id):
    db = get_database()
    dao = AccountDAO(db)
    dao.promote_posix(account_id, primary_group_id)
    db.commit()

def demote_posix(account_id):
    _demote_posix(account_id)
    msg = _("Account successfully demoted from posix.")
    queue_message(_(msg), title=_("Demote succeeded"))
    redirect_entity(account_id)
demote_posix.exposed = True

def _demote_posix(account_id):
    db = get_database()
    dao = AccountDAO(db)
    dao.demote_posix(account_id)
    db.commit()

def delete(account_id):
    """Delete account in the database."""
    db = get_database()
    dao = AccountDAO(db)
    account = dao.get_entity(account_id)
    dao.delete(account_id)
    db.commit()
    msg = _("Account '%s' successfully deleted.") % spine_to_web(account.name)
    queue_message(_(msg), title=_("Delete succeeded"))
    redirect('/account/index')
delete.exposed = True

@session_required_decorator
def leave_groups(account_id, **checkboxes):
    """Removes 'account_id' from group checked in 'checkboxes'."""
    db = get_database()
    dao = GroupDAO(db)

    count = 0
    for arg, value in checkboxes.items():
        if not arg.startswith("member_"): continue

        member_id, group_id = arg.split("_")[1:3]
        dao.remove_member(group_id, member_id)
        count += 1
            
    db.commit()
    queue_message(_("Left %s group(s)" % count), title=_("Operation succeded"))
    redirect_entity(account_id)
leave_groups.exposed = True

@session_required_decorator
def set_home(account_id, spread_id, disk_id, path):
    db = get_database()
    dao = AccountDAO(db)

    if not disk_id:
        disk_id = None

    if not path:
        path = None

    dao.set_home(account_id, spread_id, disk_id, path)
    db.commit()
    queue_message(_("Home directory set successfully."), title=_("Operation succeded"))
    redirect_entity(account_id)
set_home.exposed = True

@session_required_decorator
def remove_home(account_id, spread_id):
    db = get_database()
    dao = AccountDAO(db)
    dao.remove_home(account_id, spread_id)
    db.commit()
    queue_message(_("Home directory successfully removed."), title=_("Operation succeded"))
    redirect_entity(account_id)
remove_home.exposed = True

def set_password(id, passwd1, passwd2):
    if passwd1 != passwd2:
        queue_message(_("Passwords does not match."), title=_("Change failed"), error=True)
        redirect_entity(id)
        return

    db = get_database()
    dao = AccountDAO(db)
    dao.set_password(id, passwd1)
    db.commit()

    queue_message(_("Password successfully set."), title=_("Change succeeded"))
    redirect_entity(id)
set_password.exposed = True

@session_required_decorator
def add_affil(account_id, aff_ou, priority):
    aff_id, ou_id = aff_ou.split(":", 2)

    db = get_database()
    dao = AccountDAO(db)
    dao.add_affiliation(account_id, ou_id, aff_id, priority)
    db.commit()
    
    queue_message(_("Affiliation successfully added."), title=_("Change succeeded"))
    redirect_entity(account_id)
add_affil.exposed = True

@session_required_decorator
def remove_affil(account_id, ou_id, affil_id):
    db = get_database()
    dao = AccountDAO(db)
    dao.remove_affiliation(account_id, ou_id, affil_id)
    db.commit()

    queue_message(_("Affiliation successfully removed."), title=_("Change succeeded"))
    redirect_entity(account_id)
remove_affil.exposed = True
