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
from Cereweb.utils import url, redirect, redirect_object, queue_message
from Cereweb.utils import object_link, transaction_decorator, commit, commit_url
from Cereweb.templates.AccountSearchTemplate import AccountSearchTemplate
from Cereweb.templates.AccountViewTemplate import AccountViewTemplate
from Cereweb.templates.AccountEditTemplate import AccountEditTemplate
from Cereweb.templates.AccountCreateTemplate import AccountCreateTemplate
from Cereweb.templates.HistoryLogTemplate import HistoryLogTemplate
from Cereweb.WorkList import remember_link

import Cereweb.config
max_hits = Cereweb.config.conf.getint('cereweb', 'max_hits')

def index(req):
    """Redirects to the page with search for accounts."""
    return search(req)

def search(req, transaction, owner="", name="", expire_date="",
           create_date="", spread="", description=""):
    perform_search = False
    if owner or name or expire_date or create_date or spread or description:
        perform_search = True
        req.session['account_ls'] = (owner, name, expire_date,
                                     create_date, spread, description)
    elif 'account_ls' in req.session:
        owner, name, expire_date = req.session['account_ls'][:3]
        create_date, spread, description = req.session['account_ls'][3:]
        
    page = Main(req)
    page.title = _("Account search")
    page.setFocus("account/search")
    
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['spread'] = spread
    formvalues['expire_date'] = expire_date
    formvalues['create_date'] = create_date
    formvalues['description'] = description
    accountsearch = AccountSearchTemplate(
                       searchList=[{'formvalues': formvalues}])

    if perform_search:
        server = transaction

        entitysearch = server.get_entity_searcher()
        search = server.get_account_searcher()
        intersections = [search,]
        
        if owner:
            owner = transaction.get_entity(int(owner))
            search.set_owner(owner)

        if name:
            namesearcher = server.get_entity_name_searcher()
            namesearcher.set_name_like(name)
            namesearcher.mark_entity()
            search.set_intersections([namesearcher])

        if expire_date:
            date = server.get_commands().strptime(expire_date, "%Y-%m-%d")
            search.set_expire_date(date)

        if create_date:
            date = server.get_commands().strptime(create_date, "%Y-%m-%d")
            search.set_create_date(date)

        if description:
            if not description.startswith('*'):
                description = '*' + description
            if not description.endswith('*'):
                description += '*'
            search.set_description_like(description)

        if spread:
            accounts = sets.Set()
            spreadsearcher = server.get_spread_searcher()
            spreadsearcher.set_name_like(spread)
            for spread in spreadsearcher.search():
                searcher = server.get_entity_spread_searcher()
                searcher.set_spread(spread)
                searcher.mark_entity()
                entitysearch.set_intersections(intersections + [searcher])

                accounts.update(entitysearch.search())
        else:
            entitysearch.set_intersections(intersections)
            accounts = entitysearch.search()
  
        # Print search results
        result = html.Division(_class="searchresult")
        hits = len(accounts)
        header = html.Header('%s hits, showing 0-%s' % (hits, min(max_hits, hits)), level=3)
        result.append(html.Division(header, _class="subtitle"))
    
        table = html.SimpleTable(header="row", _class="results")
        table.add(_("Name"), _("Owner"), _("Create date"),
                  _("Expire date"), _("Actions"))

        for account in accounts[:max_hits]:
            link = object_link(account)
            owner = object_link(account.get_owner())
            cdate = account.get_create_date().strftime("%Y-%m-%d")
            edate = account.get_expire_date()
            edate = edate and edate.strftime("%Y-%m-%d") or ''
            edit = object_link(account, text="edit", method="edit",  _class="actions")
            remb = remember_link(account, _class="actions")
            table.add(link, owner, cdate, edate, str(edit)+str(remb))

        if accounts:
            result.append(table)
        else:
            error = "Sorry, no account(s) found matching the given criteria."
            result.append(html.Division(_(error), _class="searcherror"))

        result = html.Division(result)
        header = html.Header(_("Search for other account(s):"), level=3)
        result.append(html.Division(header, _class="subtitle"))
        result.append(accountsearch.form())
        page.content = result.output
    else:
        page.content = accountsearch.form

    return page
search = transaction_decorator(search)

def create(req, transaction, owner, name="", expire_date=""):
    page = Main(req)
    page.title = _("Create a new Account")
    page.setFocus("account/create")

    create = AccountCreateTemplate()

    owner = transaction.get_entity(int(owner))
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
        name = alts[0]
    
    content = create.form(owner, name, expire_date, alts, transaction)
    page.content = lambda: content
    return page
create = transaction_decorator(create)

def make(req, transaction, owner, name, expire_date="", np_type=None,
         _other=None, join=False):
    commands = transaction.get_commands()

    owner = transaction.get_entity(int(owner))
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
    commit(transaction, req, account, msg=_("Account successfully created."))
make = transaction_decorator(make)

def view(req, transaction, id, addHome=False):
    """Creates a page with a view of the account given by id, returns
       a Main-template"""
    account = transaction.get_account(int(id))
    page = Main(req)
    page.title = _("Account %s") % account.get_name()
    page.setFocus("account/view", id)
    view = AccountViewTemplate()
    content = view.viewAccount(transaction, account, addHome)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    """Creates a page with the form for editing an account."""
    account = transaction.get_account(int(id))
    page = Main(req)
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

def save(req, transaction, id, name, expire_date="", uid="",
         primary_group="", gecos="", shell=None, description="", submit=None):
    account = transaction.get_account(int(id))
    c = transaction.get_commands()
    error_msgs = []

    if submit == "Cancel":
        redirect_object(req, account, seeOther=True)
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
            queue_message(req, msg, True, object_link(account))
        redirect_object(req, account, seeOther=True)
        transaction.rollback()
    else:
        msg = _("Account successfully updated.")
        commit(transaction, req, account, msg=msg)
save = transaction_decorator(save)

def posix_promote(req, transaction, id):
    account = transaction.get_account(int(id))
    primary_group = None
    for group in account.get_groups():
        if group.is_posix():
            primary_group = group
            break
    
    if primary_group:
        searcher = transaction.get_posix_shell_searcher()
        shell = searcher.search()[0]
        account.promote_posix(primary_group, shell)
        msg = _("Account successfully promoted to posix.")
        commit(transaction, req, account, msg=msg)
    else:
        #TODO: maybe we should rather create the posix-group
        msg = "Account is not member of any posix-groups, and cannot be promoted."
        queue_message(req, _(msg), True, object_link(account))
        redirect_object(req, account, seeOther=True)
posix_promote = transaction_decorator(posix_promote)

def posix_demote(req, transaction, id):
    account = transaction.get_account(int(id))
    account.demote_posix()
    msg = _("Account successfully demoted from posix.")
    commit(transaction, req, account, msg=msg)
posix_demote = transaction_decorator(posix_demote)

def delete(req, transaction, id):
    """Delete account in the database."""
    account = transaction.get_account(int(id))
    msg = _("Account '%s' successfully deleted.") % account.get_name()
    account.delete()
    commit_url(transaction, req, url("account/index"), msg=msg)
delete = transaction_decorator(delete)

def groups(req, transaction, account_id, leave=False, create=False, **checkboxes):
    """Performs action on groups this account is member of.
    
    If leave is true: removes 'account_id' from group checked in 'checkboxes'.
    If crate is true: redirects to the create group page.
    Only one should be true at the same time.
    """
    if create:
        redirect(req, url('group/create'), seeOther=True)

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
            commit(transaction, req, account, msg=_("Left %s group(s).") % count)
        else:
            msg = _("Left no groups since none were selected.")
            queue_message(req, msg, True, object_link(account))
            redirect_object(req, account, seeOther=True)
        
    else:
        raise "I dont know what you want to do"
groups = transaction_decorator(groups)

def join_group(req, transaction, account, group_name, operation):
    """Join account into group with name 'group'."""
    account = transaction.get_account(int(account))
    operation = transaction.get_group_member_operation_type(operation)

    # find the group with the name group.
    searcher = transaction.get_entity_name_searcher()
    searcher.set_name(group_name)
    searcher.set_value_domain(transaction.get_value_domain('group_names'))
    try:
        group, = searcher.search()
        group = group.get_entity()
        assert group.get_type().get_name() == 'group'
    except:
        msg = _("Group '%s' not found") % group_name
        queue_message(req, msg, True, object_link(account))
        redirect_object(req, account, seeOther=True)
        return
    
    group.add_member(account, operation)
    
    msg = _("Joined account into group %s successfully") % group_name
    commit(transaction, req, account, msg=msg)
join_group = transaction_decorator(join_group)

def set_home(req, transaction, id, spread, home="", disk=""):
    account = transaction.get_account(int(id))
    spread = transaction.get_spread(spread)
    
    if home:
        disk = None
    elif disk:
        home = ""
        disk = transaction.get_disk(int(disk))
    else:
        queue_message(req, _("Either set home or disk"), error=True)
        redirect_object(req, account, seeOther=True)
        return
    
    account.set_homedir(spread, home, disk)
    
    msg = _("Home directory set successfully.")
    commit(transaction, req, account, msg=msg)
set_home = transaction_decorator(set_home)

def remove_home(req, transaction, id, spread):
    account = transaction.get_account(int(id))
    spread = transaction.get_spread(spread)
    account.remove_homedir(spread)
    
    msg = _("Home directory successfully removed.")
    commit(transaction, req, account, msg=msg)
remove_home = transaction_decorator(remove_home)

def set_password(req, transaction, id, passwd1, passwd2):
    account = transaction.get_account(int(id))

    if passwd1 != passwd2:
        queue_message(req, _("Passwords does not match."), error=True)
        redirect_object(req, account, seeOther=True)
    else:
        account.set_password(passwd1)
        commit(transaction, req, account, msg=_("Password successfully set."))
set_password = transaction_decorator(set_password)

# arch-tag: 4e19718e-008b-4939-861a-12bd272048df
