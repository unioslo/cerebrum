# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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
from lib.utils import queue_message, redirect, redirect_object
from lib.utils import transaction_decorator, commit
from lib.templates.EmailDomainTemplate import EmailDomainTemplate

def view(transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main()
    page.title = _("Email domain %s") % domain.get_name()
    page.setFocus("email/domain/view", id)
    template = EmailDomainTemplate()
    content = template.view_domain(transaction, domain)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main()
    page.title = _("Edit email domain %s") % domain.get_name()
    page.setFocus("email/domain/edit", id)
    template = EmailDomainTemplate()
    content = template.edit_domain(domain)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def create():
    page = Main()
    page.title = _("Create email domain")
    page.setFocus("email/domain/create")
    template = EmailDomainTemplate()
    content = template.create_domain()
    page.content = lambda: content
    return page
create.exposed = True

def list(transaction):
    page = Main()
    page.title = _("Email domains")
    page.setFocus("email/domain/list")
    template = EmailDomainTemplate()
    content = template.list_domains(transaction)
    page.content = lambda: content
    return page
list = transaction_decorator(list)
list.exposed = True
index = list

def save(transaction, name, description="", domain=None):
    if not domain:
        cmd = transaction.get_commands()
        domain = cmd.create_email_domain(name, description)
        msg = _("Created email domain %s")
    else:
        domain = transaction.get_email_domain(int(domain))
        domain.set_name(name)    
        domain.set_description(description)    
        msg = _("Saved email domain %s")
    msg = msg % domain.get_name()
    commit(transaction, domain, msg=msg)
save = transaction_decorator(save)
save.exposed = True

def remove_from_category(transaction, id, category):
    domain = transaction.get_email_domain(int(id))
    category = transaction.get_email_domain_category(category)
    domain.remove_from_category(category)
    msg = _("Removed email domain %s from category %s")
    msg = msg % (domain.get_name(), category.get_name())
    commit(transaction, domain, msg=msg)
remove_from_category = transaction_decorator(remove_from_category)    
remove_from_category.exposed = True
    
def add_to_category(transaction, id, category):
    domain = transaction.get_email_domain(int(id))
    category = transaction.get_email_domain_category(category)
    domain.add_to_category(category)
    msg = _("Added email domain %s to category %s")
    msg = msg % (domain.get_name(), category.get_name())
    commit(transaction, domain, msg=msg)
add_to_category = transaction_decorator(add_to_category)    
add_to_category.exposed = True

def addresses(transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main()
    page.title = _("Addresses in email domain %s") % domain.get_name()
    page.setFocus("email/domain/addresses", id)
    template = EmailDomainTemplate()
    content = template.list_addresses(transaction, domain)
    page.content = lambda: content
    return page
addresses = transaction_decorator(addresses)    
addresses.exposed = True

# arch-tag: b3d7db60-040d-11da-8995-abe265f82cfd
