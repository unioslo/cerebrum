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
from SpineIDL.Errors import NotFoundError, IntegrityError, PasswordGoodEnoughException

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
    
def create(transaction, **vargs):
    owner = vargs.get('owner')
    try:
        owner = transaction.get_entity(int(owner))
    except (TypeError, NotFoundError):
        owner = None

    if not owner:
        client = cherrypy.session.get('client')
        rollback_url(client, _("Please create an account through a person or group."), err=True)

    form = AccountCreateForm(transaction, **vargs)
    if len(vargs) == 1:
        return view_form(form)
    elif not form.is_correct():
        return view_form(form, form.get_error_message())
    
    make(transaction, owner, 
            vargs.get('name'),
            vargs.get('password0'),
            vargs.get('password1'),
            vargs.get('randpwd'),
            vargs.get('expire_date'),
            vargs.get('np_type'),
            vargs.get('_other'),
            vargs.get('join'),
            vargs.get('group'),
            vargs.get('description'))
create = transaction_decorator(create)
create.exposed = True

def make(transaction, owner, name, passwd0="", passwd1="", randpwd="", expire_date="", np_type=None,
         _other=None, join=False, primary_group=None, desc=""):
    commands = transaction.get_commands()
    
    password = ''
    if passwd0 and passwd1:
        password = passwd0
    else:
        password = randpwd

    referer = cherrypy.request.headerMap.get('Referer', '')
    id = owner.get_id()
    if _other:
        name = _other
    if not expire_date:
        expire_date = None
    else:
        expire_date = commands.strptime(expire_date, "%Y-%m-%d")
    if np_type:
        #assert owner.get_type().get_name() == 'group'
        assert owner.get_typestr() == 'group'
        np_type = transaction.get_account_type(np_type)
        account = owner.create_account(name, np_type, expire_date)
    else:
        try:
            account = owner.create_account(name, expire_date)
        except IntegrityError, e:
            rollback_url(referer, 'Could not create account,- possibly identical usernames.', err=True)
    if join and owner.get_typestr() == "group":
        operation = transaction.get_group_member_operation_type("union")
        owner.add_member(account, operation)

    if primary_group:
        referer = cherrypy.request.headerMap.get('Referer', '')
        try:
            primary_group = commands.get_group_by_name(primary_group)
            operation = transaction.get_group_member_operation_type("union")
            primary_group.add_member(account, operation)
            if primary_group.is_posix():
                _promote_posix(transaction, account, primary_group)
        except NotFoundError, e:
            rollback_url(referer, _("Could not find group %s.  Account is not created." % primary_group), err=True)
    if desc:
        account.set_description(desc)

    if not password:
        rollback_url(referer, 'Password is empty. Account is not created.', err=True)
    if password:
        try :
            account.set_password(password)
        except PasswordGoodEnoughException, ex:
            rollback_url(referer, 'Password is not strong enough. Account is not created.', err=True)
    commit(transaction, account, msg=_("Account successfully created."))

def view(transaction, id, **vargs):
    """Creates a page with a view of the account given by id."""
    account = transaction.get_account(int(id))
    page = AccountViewTemplate()
    page.title = _("Account %s") % account.get_name()
    page.links = _get_links()
    page.set_focus("account/view")
    page.links = _get_links()
    page.tr = transaction
    page.entity = account
    page.entity_id = account.get_id()
    return page.respond()
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id, **vargs):
    """Creates a page with the form for editing an account."""
    account = transaction.get_account(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(account)
    page.set_focus("account/edit")
    page.links = _get_links()

    vargs['id'] = id
    form = AccountEditForm(transaction, **vargs)
    if len(vargs) == 1:
        return view_form(form)
    elif not form.is_correct():
        return view_form(form, form.get_error_message())
        
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, **vargs):
    id = vargs.get('id')
    expire_date = vargs.get('expire_date')
    uid = vargs.get('uid')
    primary_group = vargs.get('group')
    gecos = vargs.get('gecos')
    shell = vargs.get('shell')
    description = vargs.get('description')
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

def _promote_posix(transaction, account, primary_group):
    searcher = transaction.get_posix_shell_searcher()
    shell = searcher.search()[0]
    uid = transaction.get_commands().get_free_uid()
    account.promote_posix(uid, primary_group, shell)

def posix_promote(transaction, id, primary_group=None):
    account = transaction.get_account(int(id))
    if not primary_group:
        for group in account.get_groups():
            if group.is_posix():
                primary_group = group
                break
    
    if primary_group:
        _promote_posix(transaction, account, primary_group)
        msg = _("Account successfully promoted to posix.")
        commit(transaction, account, msg=msg)
    else:
        #TODO: maybe we should rather create the posix-group
        msg = "Account is not member of any posix-groups, and cannot be promoted."
        queue_message(_(msg), True, object_link(account))
        redirect_object(account)
posix_promote = transaction_decorator(posix_promote)
posix_promote.exposed = True

def posix_demote(transaction, id):
    account = transaction.get_account(int(id))
    account.demote_posix()
    msg = _("Account successfully demoted from posix.")
    commit(transaction, account, msg=msg)
posix_demote = transaction_decorator(posix_demote)
posix_demote.exposed = True

def delete(transaction, id):
    """Delete account in the database."""
    account = transaction.get_account(int(id))
    msg = _("Account '%s' successfully deleted.") % account.get_name()
    account.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def groups(transaction, account_id, leave=False, create=False, **checkboxes):
    """Performs action on groups this account is member of.
    
    If leave is true: removes 'account_id' from group checked in 'checkboxes'.
    If crate is true: redirects to the create group page.
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
    spread = transaction.get_spread(spread)
    account.remove_homedir(spread)
    
    msg = _("Home directory successfully removed.")
    commit(transaction, account, msg=msg)
remove_home = transaction_decorator(remove_home)
remove_home.exposed = True

def set_password(transaction, id, passwd1, passwd2):
    account = transaction.get_account(int(id))

    if passwd1 != passwd2:
        queue_message(_("Passwords does not match."), error=True)
        redirect_object(account)
    else:
        account.set_password(passwd1)
        commit(transaction, account, msg=_("Password successfully set."))
set_password = transaction_decorator(set_password)
set_password.exposed = True

def add_affil(transaction, id, aff_ou, priority):
    account = transaction.get_account(int(id))
    aff, ou = aff_ou.split(":", 2)
    ou = transaction.get_ou(int(ou))
    aff = transaction.get_affiliation(aff)
    priority = int(priority)

    account.set_affiliation(ou, aff, priority)
    
    commit(transaction, account, msg=_("Affiliation successfully added."))
add_affil = transaction_decorator(add_affil)
add_affil.exposed = True



# arch-tag: 4e19718e-008b-4939-861a-12bd272048df
