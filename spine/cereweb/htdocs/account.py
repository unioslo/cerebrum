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
from Cereweb.utils import url, redirect, redirect_object, queue_message, snapshot
from Cereweb.templates.AccountSearchTemplate import AccountSearchTemplate
#from Cereweb.templates.AccountViewTemplate import AccountViewTemplate
#from Cereweb.templates.AccountEditTemplate import AccountEditTemplate
#from Cereweb.templates.AccountCreateTemplate import AccountCreateTemplate
#from Cereweb.templates.HistoryLogTemplate import HistoryLogTemplate


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

def search(req, name="", owner="", expire_date="", create_date=""):
    req.session['account_lastsearch'] = (name, owner,
                                         expire_date, create_date)
    page = Main(req)
    page.title = _("Account search:")
    page.setFocus("account/list")
    server = snapshot(req)
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['owner'] = owner
    formvalues['expire_date'] = expire_date
    formvalues['create_date'] = create_date
    accountsearch = AccountSearchTemplate(
                       searchList=[{'formvalues': formvalues}])
    result = html.Division()
    result.append(html.Header(_("Account search results:"), level=2))
    
    searcher = server.get_account_searcher()
    if name:
        searcher.set_name_like(name)
    if owner:
        seacher.set_owner_like(owner)
    accounts = searcher.search()
    
    table = html.SimpleTable(header="row")
    table.add(_("Name"), _("Owner"))
    for account in accounts:
        link = url("account/view?id=%s" % account.get_id())
        link = html.Anchor(account.get_name(), href=link)
        table.add(link, account.get_owner())

    if accounts:
        result.append(table)
    else:
        page.add_message(_("Sorry, no account(s) found matching " \
                           "the given criteria."))
        
    result.append(html.Header(_("Search for other account(s):"), level=2))
    result.append(accountsearch.form())
    page.content = result.output
    return page

def create(req, ownerid="", name="", affiliation="", expire_date=""):
    page = Main(req)
    page.title = _("Create a new person:")
    page.setFocus("account/create")
    server = req.session.get("active")
    # Store given createparameters in the create-form
    values = {}
    values['name'] = name
    values['affiliation'] = affiliation
    values['expire_date'] = expire_date
    create = AccountCreateTemplate(searchList=[{'formvalues': values}])
    
    if name and affiliation and expire_date:
        pass

    page.content = create.form
    return page

def _get_account(req, id):
    server = req.session.get("active")
    try:
        return server.get_account(int(id))
    except Exception, e:
        queue_message(req, _("Could not load account with id=%s") % id, error=True)
        queue_message(req, _(str(e)), error=True)
        redirect(req, url("account"), temporary=True)

def _create_view(req, id):
    """Creates a page with a view of the account given by id, returns
       a tuple of a Main-template and an account instance"""
    page = Main(req)
    page.title = ""
    account = _get_account(req, id)
    page.setFocus("account/view", id)
    view = AccountViewTemplate()
    page.content = lambda: view.viewAccount(req, account)
    return (page, account)

def view(req, id):
    (page, account) = _create_view(req, id)
    return page

def edit(req, id):
    """Creates a page with the form for editing an account."""
    account = _get_account(req, id)
    page = Main(req)
    page.title = ""
    page.setFocus("account/edit")
    edit = AccountEditTemplate()
    edit.formvalues['name'] = account.get_name()
# TODO: fetch more values from the server...
    page.content = lambda: edit.edit(account)
    return page

def save(req, id, save=None, abort=None, expire_date=''):
    pass
#    account = ClientAPI.Account.fetch_by_id(server, id)
#    owner = account.get_owner_object()
#    if not save:
#        owner = account.get_owner_object()
#        return redirect_object(req, owner, seeOther=True)
#    if expire_date:
#        # Expire date is set, check if it's changed...
#        expire_date = DateTime.DateFrom(expire_date)
#        if account.expire_date != expire_date:
#            account.set_expire_date(expire_date)
#            queue_message(req, _("Set expiration date to %s") %
#                            expire_date.Format("%Y-%m-%d"))
#    else:
#        # No expire date set, check if it's to be removed
#        if account.expire_date:
#            account.set_expire_date(None)
#            queue_message(req, _("Removed expiration date"))
#    return redirect_object(req, owner, seeOther=True)
        

def delete(req, id):
    pass
#    account = ClientAPI.Account.fetch_by_id(server, id)
#    owner = account.get_owner_object()
#    account.set_expire_date(DateTime.DateFrom('').Format('%Y-%m-%d'))
#    queue_message(req, _("Account '%s' queued for removal") % account.name)
#    return redirect_object(req, owner)

# arch-tag: 4e19718e-008b-4939-861a-12bd272048df
