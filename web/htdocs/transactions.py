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
from Cerebrum.web.Main import Main
from Cerebrum.web.utils import queue_message
from Cerebrum.web.utils import redirect
from Cerebrum.web.utils import url
from Cerebrum.web.Transactions import begin
from Cerebrum.web.templates.TransactionsTemplate import TransactionsTemplate

def _get_transaction(req, id):
    """Return the transaction object for the specific id."""
    for transaction in req.session.get("transactions", []):
        if transaction.get_id() == id:
            return transaction
    queue_message(req, _("Could not find transaction with id=%i" % id), error=True)
    redirect(req, url("transactions"), temporarly=True)

def index(req):
    """Transactions/index just redirects the user to transactions/list."""
    return list(req)

def list(req, name="", desc=""):
    """Creates a page with create-new-form and list all transactions."""
    page = Main(req)
    page.title = _("Transactions:")
    page.menu.setFocus("transactions/list")
    values = {}
    values['name'] = name
    values['desc'] = desc
    template = TransactionsTemplate(searchList=[{'formvalues': values}])
    page.content = lambda: template.index(req)
    return page

def view(req, id):
    """Show info about the transaction, and the objects it has."""
    transaction = _get_transaction(req, int(id))
    page = Main(req)
    page.title = _("View %s:" % transaction.get_name())
    page.menu.setFocus("transactions/view", str(transaction.get_id()))
    template = TransactionsTemplate()
    page.content = lambda: template.view(req, transaction)
    return page

def edit(req, id, name="", desc=""):
    """Edit the given transaction, and shows a list over all transactions."""
    transaction = _get_transaction(req, int(id))
    page = Main(req)
    page.title = _("Edit %s:" % transaction.get_name())
    page.menu.setFocus("transactions/edit", str(transaction.get_id()))
    values = {}
    values['name'] = name
    values['desc'] = desc
    template = TransactionsTemplate(searchList=[{'formvalues': values}])
    page.content = lambda: template.edit(req, transaction)
    return page

def history(req, id):
    transaction = _get_transaction(req, int(id))
    page = Main(req)
    page.title = _("History for %s:" % transaction.get_name())
    page.menu.setFocus("transactions/history", str(transaction.get_id()))
    template = TransactionsTemplate()
    page.content = lambda: template.history(req, transaction)
    return page

def select(req, submit, transaction):
    """Decide what to do, then send them back to where they were.
    
    When someone presses a button on the transaction-box in the left corner
    of the page, they end up in this method, wich then commits the action,
    and redirects them back to where they came from.
    """
    tmp_url = ""
    submit = submit.lower()
    if submit == "select":
        req.session['active'] = _get_transaction(req, int(transaction))
        tmp_url = url("transactions/list")
    elif submit == "new":
        return list(req)
    elif submit == "commit":
        active = req.session.get("active", None)
        if active:
            name = active.get_name()
            active.commit()
            queue_message(req, _("%s has been commited." % name))
        else:
            queue_message(req, _("Unable to commit transaction."), error=True)
        tmp_url = url("transactions/list")
    elif submit == "rollback":
        active = req.session.get("active", None)
        if active:
            name = active.get_name()
            active.rollback()
            queue_message(req, _("%s has been rolled back." % name))
        else:
            queue_message(req, _("Unable to rollback transaction."), error=True)
        tmp_url = url("transactions/list")

    #redirect to another page, or back to the page the user came from.
    redirect(req, tmp_url, seeOther=True)

def new(req, name, desc=""):
    """Creates a new transaction."""
    trans = begin(req, name, desc)
    queue_message(req, _("Transaction %s have been created" % trans.get_name()))
    redirect(req, url("transactions/list"), seeOther=True)

def save(req, id, name="", desc=""):
    """Change the given info for the given transaction."""
    trans = _get_transaction(req, int(id))
    trans.set_name(name)
    trans.set_description(desc)
    queue_message(req, _("Transaction %s have been modified." % trans.get_name()))
    redirect(req, url("transactions/edit?id=%i" % trans.get_id()), seeOther=True)

# arch-tag: db31a148-8eff-4e76-9ccc-a72265dffdf3
