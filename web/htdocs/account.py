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

import cerebrum_path 
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.AccountSearchTemplate import AccountSearchTemplate
from Cerebrum.web.templates.AccountViewTemplate import AccountViewTemplate
from Cerebrum.web.templates.AccountEditTemplate import AccountEditTemplate
from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url
from Cerebrum.web.utils import redirect
from Cerebrum.web.utils import redirect_object
from Cerebrum.web.utils import queue_message
from Cerebrum.web.utils import no_cache
from mx import DateTime
import xmlrpclib

def index(req):
    page = Main(req)
    page.menu.setFocus("account/search")
    accountsearch = AccountSearchTemplate()
    page.content = accountsearch.form
    return page

def list(req):
    no_cache(req)
    (name, owner, expire_date, create_date) = \
        req.session.get('account_lastsearch', ("", "", "", ""))
    return search(req, name, accountid, birthno, birthdate)

def search(req, name, owner, expire_date, create_date):
    req.session['account_lastsearch'] = (name, owner,
                                         expire_date, create_date)
    page = Main(req)
    page.title = "Account search"
    page.setFocus("account/list")
    server = req.session['server']
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['owner'] = owner
    formvalues['expire_date'] = expire_date
    formvalues['create_date'] = create_date
    accountsearch = AccountSearchTemplate(
                       searchList=[{'formvalues': formvalues}])
    result = html.Division()
    result.append(html.Header(_("Account search results"), level=2))
    accounts = ClientAPI.Account.search(server, name or None,
                                        owner or None,
                                        expire_date or None,
                                        create_date or None)
    table = html.SimpleTable(header="row")
    table.add(_("Name"), _("Owner"))
    for (id, name, owner) in accounts:
        owner = owner or ""
        link = url("account/view?id=%s" % id)
        link = html.Anchor(name, href=link)
        table.add(link, desc)
    if accounts:    
        result.append(table)
    else:
        page.add_message(_("Sorry, no account(s) found matching the given criteria."))
        
    result.append(html.Header(_("Search for other accounts"), level=2))
    result.append(accountsearch.form())
    page.content = result.output()
    return page    

def create(req, ownerid="", ownertype="", id="", name="", affiliation="", 
           expire_date="", show_form=None, hide_form=None, create=None):
    if show_form:
        req.session['profile']['person']['edit']['show_account_create'] = True

    elif hide_form:
        req.session['profile']['person']['edit']['show_account_create'] = False

    elif create:
        server = req.session['server']
        try:
            owner = ClientAPI.fetch_object_by_id(server, ownerid)
            account = ClientAPI.Account.create(server, name, owner, affiliation)
            
            if expire_date and account:
                account.set_expire_date(expire_date)
        
        except xmlrpclib.Fault, e:
            queue_message(req, e.faultString.split("CerebrumError: ")[-1], True)
        
        else:
            if not expire_date:
                expire_date = _("never")
            queue_message(req, _("Account '%s' added, expires '%s'") % (name, expire_date))
            
    return redirect(req, url("%s/view?id=%s" % (ownertype, ownerid)), seeOther=True)

def _create_view(req, id):
    """Creates a page with a view of the account given by id, returns
       a tuple of a Main-template and an account instance"""
    server = req.session['server']
    page = Main(req)
    try:
        account = ClientAPI.Account.fetch_by_id(server, id)
    except:
        page.add_message(_("Could not load account with id %s") % id)
        return (page, None)

    page.menu.setFocus("account/view", id)
    view = AccountViewTemplate()
    page.content = lambda: view.viewAccount(account)
    return (page, account)

def view(req, id):
    (page, account) = _create_view(req, id)
    return page

def edit(req, id):
    server = req.session['server']
    account = ClientAPI.Account.fetch_by_id(server, id)
    owner = account.get_owner_object()
    page = Main(req)
    page.menu.setFocus("account/edit")
    edit = AccountEditTemplate()
    if account.expire_date:
        edit.formvalues['expire_date'] = account.expire_date.Format("%Y-%m-%d")
    else:
        edit.formvalues['expire_date'] = ""    
    page.content = lambda: edit.edit(account)
    return page

def save(req, id, save=None, abort=None, expire_date=''):
    server = req.session['server']
    account = ClientAPI.Account.fetch_by_id(server, id)
    owner = account.get_owner_object()
    if not save:
        owner = account.get_owner_object()
        return redirect_object(req, owner, seeOther=True)
    if expire_date:
        # Expire date is set, check if it's changed...
        expire_date = DateTime.DateFrom(expire_date)
        if account.expire_date != expire_date:
            account.set_expire_date(expire_date)
            queue_message(req, _("Set expiration date to %s") %
                            expire_date.Format("%Y-%m-%d"))
    else:
        # No expire date set, check if it's to be removed
        if account.expire_date:
            account.set_expire_date(None)
            queue_message(req, _("Removed expiration date"))
    return redirect_object(req, owner, seeOther=True)
               

        

def delete(req, id):    
    server = req.session['server']
    account = ClientAPI.Account.fetch_by_id(server, id)
    owner = account.get_owner_object()
    account.set_expire_date(DateTime.DateFrom('').Format('%Y-%m-%d'))
    queue_message(req, _("Account '%s' queued for removal") % account.name)
    return redirect_object(req, owner)

# arch-tag: 2af5c9c4-0d57-41c8-9c72-846d5adfec0e
