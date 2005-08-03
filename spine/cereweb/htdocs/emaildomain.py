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

import sets
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator, object_link
from Cereweb.WorkList import remember_link
from Cereweb.templates.EmailDomain import EmailDomain


def index(req):
    # Could also let people search by email address etc
    return redirect(req, url('emaildomain/list'))

def view(req, transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main(req)
    page.title = _("Email domain %s") % domain.get_name()
    page.setFocus("email/domain/view", id)
    template = EmailDomain()
    content = template.view_domain(transaction, domain)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

def list(req, transaction):
    page = Main(req)
    page.title = _("Email domains")
    page.setFocus("email/domain/list")
    template = EmailDomain()
    content = template.list_domains(transaction)
    page.content = lambda: content
    return page
list = transaction_decorator(list)

def remove_from_category(req, transaction, id, category):
    domain = transaction.get_email_domain(int(id))
    category = transaction.get_email_domain_category(category)
    domain.remove_from_category(category)
    msg = _("Removed email domain %s from category %s")
    msg = msg % (domain.get_name(), category.get_name())
    redirect_object(req, domain)
    transaction.commit() 
    queue_message(req, msg)
remove_from_category = transaction_decorator(remove_from_category)    
    

def add_to_category(req, transaction, id, category):
    domain = transaction.get_email_domain(int(id))
    category = transaction.get_email_domain_category(category)
    domain.add_to_category(category)
    msg = _("Added email domain %s to category %s")
    msg = msg % (domain.get_name(), category.get_name())
    redirect_object(req, domain)
    transaction.commit() 
    queue_message(req, msg)
add_to_category = transaction_decorator(add_to_category)    

def addresses(req, transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main(req)
    page.title = _("Addresses in email domain %s") % domain.get_name()
    page.setFocus("email/domain/addresses", id)
    template = EmailDomain()
    content = template.addresses(transaction, domain)
    page.content = lambda: content
    return page
addresses = transaction_decorator(addresses)    

