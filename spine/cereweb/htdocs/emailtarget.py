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
from lib.utils import transaction_decorator, object_link, commit, commit_url
from lib.templates.EmailDomain import EmailDomain
from lib.templates.EmailTarget import EmailTarget
from SpineIDL.Errors import NotFoundError

def view(transaction, id):
    target = transaction.get_email_target(int(id))
    page = Main()
    page.title = _("Email target") 
    try:
        primary = target.get_primary_address()
    except NotFoundError:
        pass
    else:
        page.title += " " + primary.full_address()
    page.setFocus("email/target/view", id)
    template = EmailTarget()

    if not target.get_addresses() and target.get_entity():
        #FIXME: Should use Cerebrum methods to suggest email address    
        suggestion = target.get_entity().get_name()
    else:
        suggestion = ""   
    
    content = template.view_target(transaction, target, suggestion)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    target = transaction.get_email_target(int(id))
    page = Main()
    page.title = _("Email target") 
    try:
        primary = target.get_primary_address()
    except NotFoundError:
        pass    
    else:
        page.title += " " + primary.full_address()    
    page.setFocus("email/target/edit", id)
    template = EmailTarget()
    content = template.edit_target(transaction, target)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def create(transaction):
    page = Main()
    page.title = _("Create email target") 
    page.setFocus("email/target/create")
    template = EmailTarget()
    content = template.create_target(transaction)
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True
index = create

def creation(transaction, target_type, entity=None):
    target_type = transaction.get_email_target_type(target_type)    
    target = transaction.get_commads().create_email_target(target_type)
    if entity:
        entity = transaction.get_entity(int(entity))
        target.set_entity(entity) 
        if entity.get_type().get_name() == "account" and entity.is_posix():
            target.set_using(entity)
        queue_message(_("Set target entity to %s") % object_link(entity))
        
    msg = _("Created email target of type %s") % target_type.get_name()
    commit(transaction, target, msg=msg)
creation = transaction_decorator(creation)
creation.exposed = True

def save(transaction, id, target_type, using=None, alias=""):
    target_type = transaction.get_email_target_type(target_type)    
    target = transaction.get_email_target(int(id))
    if target.get_type() != target_type:
        target.set_type(target_type)
    old_using = target.get_using()
    if old_using is not None:
        old_using = old_using.get_name()
    if old_using != using:
        if using is not None:
            using = transaction.get_commands().get_account_by_name(using)
        target.set_using(using)
    if target.get_alias() != alias:
        target.set_alias(alias)    
    msg = _("Email target successfully updated.")
    commit(transaction, target, msg=msg)
save = transaction_decorator(save)
save.exposed = True

def delete(transaction, id):
    target = transaction.get_email_target(int(id))
    entity = target.get_entity()
    if entity:
        redirect_object(entity)
    else:
        redirect('/')
    target.delete()
    msg = _("Deleted email target")
    transaction.commit()
    queue_message(msg)
delete = transaction_decorator(delete)
delete.exposed = True

def add_address(transaction, local_part, domain, target):
    target = transaction.get_email_target(int(target))
    domain = transaction.get_email_domain(int(domain))
    cmd = transaction.get_commands()
    addr = cmd.create_email_address(local_part, domain, target)
    queue_message(_("Added email address %s") % addr.full_address())
    _check_primary(target)
    redirect_object(target)
    transaction.commit()
add_address = transaction_decorator(add_address)    
add_address.exposed = True

def set_primary(transaction, id, address=None):
    target = transaction.get_email_target(int(id))
    if address:
        address = transaction.get_email_address(int(address))
    # else: set to none, ie. unset primary    
    target.set_primary_address(address)    
    if address is None:
        queue_message(_("Unset primary email address"))
    else:    
        queue_message(_("Set %s as primary email address") % address.full_address())
    redirect_object(target)
    transaction.commit()
set_primary = transaction_decorator(set_primary)        
set_primary.exposed = True

def _check_primary(target):
    # FIXME: Is this a business rule?
    try:
        target.get_primary_address()
    except NotFoundError:    
        rest = target.get_addresses()
        if len(rest) == 1:
            rest[0].set_as_primary()
            queue_message(_("Set %s as primary address of target") % rest[0].full_address())
        elif rest:
            queue_message(_("You should select one of the remaining "
                                 "addresses as the new primary address."))

def remove_address(transaction, id, address):
    target = transaction.get_email_target(int(id))
    address = transaction.get_email_address(int(address))
    msg = _("Removed address %s") % address.full_address()
    queue_message(msg)
    address.delete()
    _check_primary(target)
    redirect_object(target)
    transaction.commit()
remove_address = transaction_decorator(remove_address)
remove_address.exposed = True

def edit_address(transaction, id, address):
    #target = transaction.get_email_target(int(id))
    address = transaction.get_email_address(int(address))
    page = Main()
    page.title = _("Edit email address %s") % address.full_address() 
    page.setFocus("email/target/edit_address", id)
    template = EmailTarget()
    content = template.edit_address(transaction, address)
    page.content = lambda: content
    return page
edit_address = transaction_decorator(edit_address)
edit_address.exposed = True

def save_address(transaction, address, local_part, domain):
    address = transaction.get_email_address(int(address))
    domain = transaction.get_email_domain(int(domain))
    address.set_local_part(local_part)
    address.set_domain(domain)
    msg = _("Saved address %s") % address.full_address()
    redirect_object(address.get_target())
    transaction.commit()
    queue_message(msg)
save_address = transaction_decorator(save_address)
save_address.exposed = True

def search(transaction, address=""):
    if address:
        cmd = transaction.get_commands()
        addr = cmd.find_email_address(address)        
        if addr:
            redirect_object(addr.get_target())    
            return
        else:
            queue_message(_("Could not find email address %s") % address)    
    page = Main()
    page.title = _("Search for email target") 
    #page.setFocus("email/target/search", id)
    template = EmailTarget()
    content = template.find_email(address)
    page.content = lambda: content
    return page
search = transaction_decorator(search)
search.exposed = True

# arch-tag: 53b597b2-0472-11da-9196-788d6ec686ec
