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

import forgetHTML as html
from gettext import gettext as _
from Cerebrum import Errors
from Cereweb.Main import Main
from Cereweb.utils import url, redirect, redirect_object, queue_message
from Cereweb.utils import object_link, transaction_decorator
from Cereweb.templates.AccountSearchTemplate import AccountSearchTemplate
from Cereweb.templates.AccountViewTemplate import AccountViewTemplate
from Cereweb.templates.AccountEditTemplate import AccountEditTemplate
from Cereweb.templates.AccountCreateTemplate import AccountCreateTemplate
from Cereweb.templates.HistoryLogTemplate import HistoryLogTemplate


def index(req):
    page = Main(req)
    page.title = _("Search for account(s):")
    page.setFocus("account/search")
    accountsearch = AccountSearchTemplate()
    page.content = accountsearch.form
    return page

def list(req):
    (name, owner, expire_date, create_date) = \
        req.session.get('account_lastsearch', ("", "", "", ""))
    return search(req, name, owner, expire_date, create_date)

def search(req, name="", owner="", expire_date="", create_date="", transaction=None):
    req.session['account_lastsearch'] = (name, owner,
                                         expire_date, create_date)
    page = Main(req)
    page.title = _("Account search:")
    page.setFocus("account/list")
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['owner'] = owner
    formvalues['expire_date'] = expire_date
    formvalues['create_date'] = create_date
    accountsearch = AccountSearchTemplate(
                       searchList=[{'formvalues': formvalues}])

    if name or owner or expire_date or create_date:
        server = transaction

        entitysearch = server.get_entity_searcher()
        search = server.get_account_searcher()
        intersections = [search,]
        

        if name:
            namesearcher = server.get_entity_name_searcher()
            namesearcher.set_name_like(name)
            namesearcher.mark_entity()
            search.set_intersections([namesearcher])

        if owner:
            personnamesearch = server.get_person_name_searcher()
            personnamesearch.set_name_like(owner)
            personnamesearch.mark_person()
            intersections.append(personnamesearch)
        
        if expire_date:
            date = server.get_commands().strptime(expire_date, "%Y-%m-%d")
            search.set_expire_date(date)

        if create_date:
            date = server.get_commands().strptime(create_date, "%Y-%m-%d")
            search.set_create_date(date)

        entitysearch.set_intersections(intersections)
        accounts = entitysearch.search()
   
        if accounts:
            result = html.Division()
            result.append(html.Header(_("Account search results:"), level=2))
        
            table = html.SimpleTable(header="row")
            table.add(_("Name"), _("Owner"), _("Create date"),
                      _("Expire date"), _("Description"))

            for account in accounts:
                link = url("account/view?id=%s" % account.get_id())
                link = html.Anchor(account.get_name(), href=link)
                owner = object_link(account.get_owner())
                cdate = account.get_create_date().strftime("%Y-%m-%d")
                edate = account.get_expire_date()
                if edate:
                    edate = edate.strftime("%Y-%m-%d")
                else:
                    edate = ''
                #table.add(link, owner, cdate, edate, account.get_description())
                table.add(link, owner, cdate, edate, account.get_description())

            result.append(table)
            result.append(html.Header(_("Search for other account(s):"), level=2))
            result.append(accountsearch.form())
            page.content = result.output
        else:
            page.add_message(_("Sorry, no account(s) found matching " \
                               "the given criteria."))
            page.content = lambda: accountsearch.form()
    else:
        page.content = lambda: accountsearch.form()

    return page
search = transaction_decorator(search)

def create(req, transaction, owner, name="", expire_date=""):
    page = Main(req)
    page.title = _("Create a new Account:")
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
        first = "fisk"
        last = "frosk"

    alts = transaction.get_commands().suggest_usernames(first, last)

    if not name:
        name = alts[0]
    
    content = create.form(owner, name, expire_date, alts)
    page.content = lambda: content
    return page
create = transaction_decorator(create)

def make(req, transaction, owner, name, expire_date=""):
    commands = transaction.get_commands()

    owner = transaction.get_entity(int(owner))
    if not expire_date:
        expire_date = commands.get_date_none()
    else:
        expire_date = commands.strptime(expire_date, "%Y-%m-%d")

    account = commands.create_account(name, owner, expire_date)
    redirect_object(req, account)
    transaction.commit()
make = transaction_decorator(make)


def view(req, transaction, id):
    """Creates a page with a view of the account given by id, returns
       a Main-template"""
    page = Main(req)
    page.title = ""
    account = transaction.get_account(int(id))
    page.setFocus("account/view", id)
    view = AccountViewTemplate()
    content = view.viewAccount(req, account)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def edit(req, transaction, id):
    """Creates a page with the form for editing an account."""
    account = transaction.get_account(int(id))
    page = Main(req)
    page.title = ""
    page.setFocus("account/edit")
    
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
        groups = [(i.get_id(), i.get_name()) for i in account.get_groups()]

    # shells which the user can change on the account
    shell_searcher = transaction.get_posix_shell_searcher()
    shells = [(i.get_name(), i.get_name())
                    for i in shell_searcher.search()]
        
    content = edit.edit(account, groups, shells)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def save(req, transaction, id, name, expire_date="", uid="",
         primary_group="", gecos="", shell=None):
    account = transaction.get_account(int(id))
    c = transaction.get_commands()
    error_msgs = []

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
            queue_message(req, msg, error=True)
        redirect_object(req, account, seeOther=True)
        transaction.rollback()
    else:
        redirect_object(req, account, seeOther=True)
        transaction.commit()
        queue_message(req, _("Group successfully updated."))
save = transaction_decorator(save)

def delete(req, id):
    pass

# arch-tag: 4e19718e-008b-4939-861a-12bd272048df
