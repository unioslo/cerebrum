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

import Menu
import utils
from gettext import gettext as _


class FixUrlMixin:
    def addItem(self, name, label, url):
            # i18n and fix url
            label = _(label)
            url = utils.url(url)    
            item = MenuItem(name, label, url) 
            self.addMenuItem(item) 
            return item

class MenuItem(FixUrlMixin, Menu.MenuItem):
    def __init__(self, *args, **kwargs):
        Menu.MenuItem.__init__(self, *args, **kwargs)

class SideMenu(FixUrlMixin, Menu.Menu):
    def __init__(self):
        Menu.Menu.__init__(self)
        self.makeMain()
        self.makePerson()
        self.makeAccount()
        self.makeGroup()
        #self.makeRoles()
        #self.makeSpread()
        self.makeTransactions()
        self.makeOptions()

    def makeMain(self):
        self.main = self.addItem("main", "Main", "index")

    def makePerson(self):
        self.person = self.addItem("person", "Person", "person")
        self.person.addItem("search", "Search", "person/search")
        self.person.addItem("list", "List", "person/list")
        self.person.addItem("create", "Create", "person/create")
        self.person.addItem("view", "View", "person/view?id=%s")
        self.person.addItem("edit", "Edit", "person/edit?id=%s")
    
    def makeAccount(self):
        self.account = self.addItem("account", "Account", "account")
        self.account.addItem("search", "Seach", "account/search")
        self.account.addItem("list", "List", "account/list")
        self.account.addItem("create", "Create", "account/create")

    def makeGroup(self):    
        self.group = self.addItem("group", "Group", "group")
        self.group.addItem("search", "Search", "group")
        self.group.addItem("list", "List", "group/list")
        self.group.addItem("create", "Create", "group/create")
        self.group.addItem("view", "View", "group/view?id=%s")
        self.group.addItem("edit", "Edit", "group/edit?id=%s")

    def makeRoles(self):
        self.group = self.addItem("roles", "Roles", "roles")
        self.group.addItem("search", "Search", "roles/search")
        self.group.addItem("list", "List", "roles/list")
        self.group.addItem("view", "View", "roles/view?id=%s")
        self.group.addItem("edit", "Edit", "roles/edit?id=%s")

    def makeSpread(self):
        self.group = self.addItem("spread", "Spread", "spread")
        self.group.addItem("search", "Search", "spread/search")
        self.group.addItem("list", "List", "spread/list")
        self.group.addItem("view", "View", "spread/view?id=%s")
        self.group.addItem("edit", "Edit", "spread/edit?id=%s")

    def makeTransactions(self):
        self.transactions = self.addItem("transactions", "Transactions", "transactions")
        self.transactions.addItem("list", "List", "transactions/list")
        self.transactions.addItem("view", "View", "transactions/view?id=%s")
        self.transactions.addItem("edit", "Edit", "transactions/edit?id=%s")
        self.transactions.addItem("history", "History", "transactions/history?id=%s")

    def makeOptions(self):
        self.group = self.addItem("options", "Options", "options")
        self.group.addItem("view", "View", "options/view")
        self.group.addItem("edit", "Edit", "options/edit")

# arch-tag: dc75bf5e-9c21-42dd-9157-aa2baeb09ab0
