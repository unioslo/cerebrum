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
from lib.utils import *
from lib.Searchers import AccountSearcher
from lib.Forms import AccountCreateForm, AccountEditForm
from lib.templates.FormTemplate import FormTemplate
from lib.templates.SearchTemplate import SearchTemplate
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

from group import get_database

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
    page.account = AccountDAO().get(id)
    page.account.traits = []
    page.account.history = HistoryDAO().get_entity_history_tail(id)
    page.affiliations = PersonDAO().get_affiliations(page.account.owner.id)
    page.shells = ConstantsDAO().get_shells()
    page.groups = GroupDAO().get_entities_for_account(id)
    page.disks = DiskDAO().get_disks()
    page.email_target_types = ConstantsDAO().get_email_target_types()
    page.email_servers = HostDAO().get_email_servers()
    page.targets = HostDAO().get_email_targets(id)
    page.spreads = ConstantsDAO().get_user_spreads()

    return page.respond()
view.exposed = True

def form_edit(form, message=None):
    page = FormTemplate()
    if message:
        page.messages.append(message)
    page.title = form.get_title()
    page.set_focus("account/edit")
    page.links = _get_links()
    page.form_fields = form.get_fields()
    page.form_action = form.get_action()
    return page.respond()

def edit(transaction, id, **vargs):
    """Creates a page with the form for editing an account."""
    account = transaction.get_account(int(id))
    name = spine_to_web(account.get_name())
    expire_date = account.get_expire_date()
    description = account.get_description()
    if expire_date:
        expire_date = html_quote(expire_date.strftime('%Y-%m-%d'))
    else:
        expire_date = ''
    if description:
        description = spine_to_web(description.strip())
    else:
        description = ''
    values = {
        'id' : html_quote(id),
        'expire_date': expire_date,
        'description' : description,
    } 
    values.update(vargs)
    form = AccountEditForm(transaction, **values)
    form.title = 'Edit ' + object_link(account, text=name)
    if not vargs:
        print 'form_edit(form)'
        return form_edit(form)
    if not form.has_required() or not form.is_correct():
        print 'form not correct'
        return form_edit(form, message=form.get_error_message())
    else:
        vargs = form.get_values()
        save(transaction, vargs)
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, **vargs):
    id = vargs.get('id')
    expire_date = vargs.get('expire_date')
    uid = vargs.get('uid')
    primary_group = vargs.get('group')
    gecos = web_to_spine(vargs.get('gecos'))
    shell = web_to_spine(vargs.get('shell'))
    description = web_to_spine(vargs.get('description'))
    submit = vargs.get('submit')

    account = transaction.get_account(int(id))
    c = transaction.get_commands()
    error_msgs = []

    if submit == "Cancel":
        redirect_object(account)
        return

    if expire_date:
        expire_date = c.strptime(expire_date, "%Y-%m-%d")
    else:
        expire_date = None

    if shell is not None:
        shell_searcher = transaction.get_posix_shell_searcher()
        shell_searcher.set_name(shell)
        shells = shell_searcher.search()

        if len(shells) == 1:
            shell = shells[0]
        else:
            error_msgs.append("Error, no such shell: %s" % shell)
        
    account.set_expire_date(expire_date)
    account.set_description(description)

    if account.is_posix():
        if uid:
            account.set_posix_uid(int(uid))

        if shell:
            account.set_shell(shell)

        if primary_group:
            for group in account.get_groups():
                if group.get_id() == int(primary_group):
                    account.set_primary_group(group)
                    break
            else:
                error_msgs.append("Error, primary group not found.")
        
        account.set_gecos(gecos)

    if error_msgs:
        for msg in error_msgs:
            queue_message(msg, True, object_link(account))
        redirect_object(account)
        transaction.rollback()
    else:
        msg = _("Account successfully updated.")
        commit(transaction, account, msg=msg)
save = transaction_decorator(save)
save.exposed = True

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

def groups(transaction, account_id, leave=False, create=False, **checkboxes):
    """Performs action on groups this account is member of.
    
    If leave is true: removes 'account_id' from group checked in 'checkboxes'.
    If create is true: redirects to the create group page.
    Only one should be true at the same time.
    """
    if create:
        redirect('/group/create')

    elif leave:
        account = transaction.get_account(int(account_id))
        operation = transaction.get_group_member_operation_type("union")
        count = 0
        for arg, value in checkboxes.items():
            if arg.startswith("member_"):
                member_id, group_id = arg.split("_")[1:3]
                member = transaction.get_account(int(member_id))
                group = transaction.get_group(int(group_id))
                group_member = transaction.get_group_member(group, 
                            operation, member, member.get_type())
                group.remove_member(group_member)
                count += 1
                
        if count > 0:
            commit(transaction, account, msg=_("Left %s group(s).") % count)
        else:
            msg = _("Left no groups since none were selected.")
            queue_message(msg, True, object_link(account))
            redirect_object(account)
        
    else:
        raise "I dont know what you want to do"
groups = transaction_decorator(groups)
groups.exposed = True

def set_home(transaction, id, spread, home="", disk=""):
    account = transaction.get_account(int(id))
    spread = transaction.get_spread(spread)
    
    if home:
        disk = None
    elif disk:
        home = ""
        disk = transaction.get_disk(int(disk))
    else:
        queue_message(_("Either set home or disk"), error=True)
        redirect_object(account)
        return
    
    account.set_homedir(spread, home, disk)
    
    msg = _("Home directory set successfully.")
    commit(transaction, account, msg=msg)
set_home = transaction_decorator(set_home)
set_home.exposed = True

def remove_home(transaction, id, spread):
    account = transaction.get_account(int(id))
    spread = transaction.get_spread(web_to_spine(spread))
    account.remove_homedir(spread)
    
    msg = _("Home directory successfully removed.")
    commit(transaction, account, msg=msg)
remove_home = transaction_decorator(remove_home)
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

def add_affil(transaction, id, aff_ou, priority):
    account = transaction.get_account(int(id))
    aff, ou = aff_ou.split(":", 2)
    ou = transaction.get_ou(int(ou))
    aff = transaction.get_person_affiliation_type(web_to_spine(aff))
    priority = int(priority)

    account.set_affiliation(ou, aff, priority)
    
    commit(transaction, account, msg=_("Affiliation successfully added."))
add_affil = transaction_decorator(add_affil)
add_affil.exposed = True


def remove_affil(transaction, id, ou, affil):
    account = transaction.get_account(int(id))
    ou = transaction.get_ou(int(ou))
    affil = transaction.get_person_affiliation_type(web_to_spine(affil))

    account.remove_affiliation(ou, affil)

    commit(transaction, account, msg=_("Affiliation successfully removed."))
remove_affil = transaction_decorator(remove_affil)
remove_affil.exposed = True
 
def print_contract(transaction, id, lang):
    from lib.CerebrumUserSchema import CerebrumUserSchema
    tr = transaction
    referer = cherrypy.request.headerMap.get('Referer', '')
    account = tr.get_account(int(id))
    owner = account.get_owner()
    names = owner.get_names()
    lastname = None
    firstname = None
    for name in names:
        nameVariant = name.get_name_variant()
        sourceSystem = name.get_source_system()
        if sourceSystem.get_name() == 'Cached':
            if nameVariant.get_name() == 'LAST':
                lastname = from_spine_decode(name.get_name())
            if nameVariant.get_name() == 'FIRST':
                firstname = from_spine_decode(name.get_name())
    targetSearcher = tr.get_email_target_searcher()
    targetSearcher.set_target_entity(account)
    emailTargets = targetSearcher.search()
    emailAddress = None
    if emailTargets:
        ## which one to choose?
        primaryEmail = emailTargets[0].get_primary_address()
        if primaryEmail:
            domain  = primaryEmail.get_domain().get_name()
            emailAddress = from_spine_decode(primaryEmail.get_local_part()) + '@' +from_spine_decode(domain)
    username = from_spine_decode(account.get_name())
    passwd = None
    birthdate = owner.get_birth_date().strftime('%d-%m-%Y')
    studyprogram = None
    year = None
    affiliation = None
    affiliations = owner.get_affiliations()
    if affiliations:
        for aff in affiliations:
            if not aff.marked_for_deletion():
                affiliation = aff
    perspective  = transaction.get_ou_perspective_type('Kjernen')   
    faculty = None
    department = None
    if affiliation:
        faculty = from_spine_decode(affiliation.get_ou().get_parent(perspective).get_name())
        department = from_spine_decode(affiliation.get_ou().get_name())
    else:
        rollback_url(referer, 'User has no affiliation.', err=True)
    ## print 'lastename = ', lastname
    ## print 'firstname = ', firstname
    ## print 'email = ', emailAddress
    ## print 'username = ', username
    ## print 'passwd = ', passwd
    ## print 'birthdate = ', birthdate
    ## print 'studyprogram = ', studyprogram
    ## print 'year = ', year
    ## print 'faculty = ', faculty
    ## print 'department = ', department
    ## print 'lang = ', lang
    pdfSchema= CerebrumUserSchema(lastname, firstname, emailAddress, username, passwd, birthdate, studyprogram, year, faculty, department, lang)
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
        tr.rollback()
        return pdfContent
    else:
        rollback_url(referer, 'Could not make a contract.', err=True)
print_contract = transaction_decorator(print_contract)
print_contract.exposed = True
