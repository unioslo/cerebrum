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
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['owner'] = owner
    formvalues['expire_date'] = expire_date
    formvalues['create_date'] = create_date
    accountsearch = AccountSearchTemplate(
                       searchList=[{'formvalues': formvalues}])


    if name or owner or expire_date or create_date:
        server = snapshot(req)

        entitysearch = server.get_entity_searcher()
        accountsearch = server.get_account_searcher()
        intersections = [accountsearch,]
        
        if name:
            accountsearch.set_name_like(name)

        if owner:
            personnamesearch = server.get_person_name_searcher()
            personnamesearch.set_name_like(owner)
            personnamesearch.mark_person()
            intersections.append(personnamesearch)
        
        if expire_date:
            date = server.get_commands().strptime(expire_date, "%Y-%m-%d")
            accountsearch.set_expire_date(date)

        if create_date:
            date = server.get_commands().strptime(create_date, "%Y-%m-%d")
            accountsearch.set_create_date(date)

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
                owner = account.get_owner().get_names()[0].get_name()
                cdate = account.get_create_date().strftime("%Y-%m-%d")
                edate = account.get_expire_date().strftime("%Y-%m-%d")
                table.add(link, owner, cdate, edate, account.get_description())

            result.append(table)
            result.append(html.Header(_("Search for other account(s):"), level=2))
            result.append(accountsearch.form())
            page.content = result.output
        else:
            page.add_message(_("Sorry, no account(s) found matching " \
                               "the given criteria."))
            page.content = lambda: accountsearch.form()

    return page

def create(req, owner="", name="", expire_date=""):
    page = Main(req)
    page.title = _("Create a new person:")
    page.setFocus("account/create")

    # Store given createparameters in the create-form
    values = {}
    values['owner'] = owner
    values['name'] = name
    values['expire_date'] = expire_date
    create = AccountCreateTemplate(searchList=[{'formvalues': values}])
    
    page.content = create.form
    return page

def _get_account(req, id):
    server = req.session.get("active")
    try:
        return server.get_account(int(id))
    except Exception, e:
        queue_message(req, _("Could not load account with id=%i" % id), error=True)
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
    page.content = lambda: edit.edit(account)
    return page

def save(req, id, save=None, abort=None, expire_date=''):
    pass

def delete(req, id):
    pass

# arch-tag: 4e19718e-008b-4939-861a-12bd272048df
