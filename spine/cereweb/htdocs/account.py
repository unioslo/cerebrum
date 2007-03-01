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
from lib.WorkList import remember_link
from lib.Searchers import AccountSearcher
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.AccountViewTemplate import AccountViewTemplate
from lib.templates.AccountEditTemplate import AccountEditTemplate
from lib.templates.AccountCreateTemplate import AccountCreateTemplate

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("Account")
    page.setFocus("account/search")
    page.search_title = _('account(s)')
    page.search_fields = [
                  ("name", _("Account name")),
                  ("spread", _("Spread name")),
                  ("create_date", _("Created date *")),
                  ("expire_date", _("Expire date *")),
                  ("description", _("Description")),
                ]
    page.search_help = [_("Created date (YYYY-MM-DD, exact match)"),
                 _("Expired date (YYYY-MM-DD, exact match)")]
    page.search_action = '/account/search'
    page.form_values = remembered
    return page.respond()

def search(transaction, **vargs):
    """Search for accounts and display results and/or searchform.""" 
    args = ('name', 'spread', 'create_date', 'expire_date', 'description')
    searcher = AccountSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = transaction_decorator(search)
search.exposed = True
index = search

def create(transaction, owner=None, name="", expire_date=""):
    page = Main()
    page.title = _("Create a new Account")
    page.setFocus("account/create")
    page.add_jscript("find_owner.js")

    create = AccountCreateTemplate()

    try:
        owner = transaction.get_entity(int(owner))
    except TypeError, e:
        owner = ''

    if owner:
        if owner.get_type().get_name() == 'person':
            full_name = owner.get_cached_full_name().split()
            if len(full_name) == 1:
                first = ''
                last, = full_name
            else:
                first, last = full_name[0], full_name[-1]
        else:
            first = ""
            last = owner.get_name()

        alts = transaction.get_commands().suggest_usernames(first, last)
        if not name:
            name = alts and alts[0] or ''
        content = create.form(owner, name, expire_date, alts, transaction)
        page.content = lambda: content
    else:
        page.content = create.select_owner
    return page
create = transaction_decorator(create)
create.exposed = True

def make(transaction, id, name, expire_date="", np_type=None,
         _other=None, join=False):
    commands = transaction.get_commands()

    owner = transaction.get_entity(int(id))
    if name == "_other":
        name = _other
    if not expire_date:
        expire_date = commands.get_date_none()
    else:
        expire_date = commands.strptime(expire_date, "%Y-%m-%d")
    if np_type:
        np_type = transaction.get_account_type(np_type)
        account = commands.create_np_account(name, owner, np_type, expire_date)
    else:
        account = commands.create_account(name, owner, expire_date)
    if join and owner.get_type().get_name() == "group":
        operation = transaction.get_group_member_operation_type("union")
        owner.add_member(account, operation)
    commit(transaction, account, msg=_("Account successfully created."))
make = transaction_decorator(make)
make.exposed = True

def view(transaction, id, **vargs):
    """Creates a page with a view of the account given by id."""
    account = transaction.get_account(int(id))
    page = Main()
    page.title = _("Account %s") % account.get_name()
    page.setFocus("account/view", id)
    content = AccountViewTemplate().view(transaction, account)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing an account."""
    account = transaction.get_account(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(account)
    page.setFocus("account/edit", id)

    edit = AccountEditTemplate()
    edit.formvalues['name'] = account.get_name()
    if account.get_expire_date():
        edit.formvalues['expire_date'] = account.get_expire_date().strftime("%Y-%m-%d")
    if account.is_posix():
        edit.formvalues['uid'] = account.get_posix_uid()
        edit.formvalues['primary_group'] = account.get_primary_group().get_id()
        edit.formvalues['gecos'] = account.get_gecos()
        edit.formvalues['shell'] = account.get_shell().get_name()

    # groups which the user can have as primary group
    groups = ()
    if account.is_posix():
        groups = [(i.get_id(), i.get_name())
                    for i in account.get_groups() if i.is_posix()]

    # shells which the user can change on the account
    shell_searcher = transaction.get_posix_shell_searcher()
    shells = [(i.get_name(), i.get_name())
                    for i in shell_searcher.search()]
        
    content = edit.edit(account, groups, shells)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, name, expire_date="", uid="",
         primary_group="", gecos="", shell=None, description="", submit=None):
    account = transaction.get_account(int(id))
    c = transaction.get_commands()
    error_msgs = []

    if submit == "Cancel":
        redirect_object(account)
        return

    if expire_date:
        expire_date = c.strptime(expire_date, "%Y-%m-%d")
    else:
        expire_date = c.get_date_none()

    if shell is not None:
        shell_searcher = transaction.get_posix_shell_searcher()
        shell_searcher.set_name(shell)
        shells = shell_searcher.search()

        if len(shells) == 1:
            shell = shells[0]
        else:
            error_msgs.append("Error, no such shell: %s" % shell)
        
    account.set_name(name)
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

def posix_promote(transaction, id):
    account = transaction.get_account(int(id))
    primary_group = None
    for group in account.get_groups():
        if group.is_posix():
            primary_group = group
            break
    
    if primary_group:
        searcher = transaction.get_posix_shell_searcher()
        shell = searcher.search()[0]
        uid = transaction.get_commands().get_free_uid()
        account.promote_posix(uid, primary_group, shell)
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
