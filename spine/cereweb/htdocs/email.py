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
import sys

import forgetHTML as html
from gettext import gettext as _
from lib.Main import Main
from lib.utils import queue_message, redirect, redirect_object, object_link
from lib.utils import transaction_decorator, commit, commit_url
from lib.utils import rollback_url, legal_domain_format
from lib.utils import legal_domain_chars
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.SearchResultTemplate import SearchResultTemplate
from lib.templates.EmailTargetTemplate import EmailTargetTemplate
from lib.templates.EmailDomainTemplate import EmailDomainTemplate

def index(transaction):
    page = Main()
    page.title = _('Email domains') 
    page.setFocus('email')
    target_template = EmailTargetTemplate()
    domain_template = EmailDomainTemplate()
    
    content = html.Division()
    content.append(domain_template.search_box(transaction))
    content.append(domain_template.create_box(transaction))
    content.append(target_template.find_email())
    page.content = content.output
    return page
index = transaction_decorator(index)    
index.exposed = True

def search(transaction, **vargs):
    page = Main()
    page.title = _("Search for email domain(s)")
    page.setFocus("email/search")
    page.add_jscript("search.js")

    form = lambda values: EmailDomainTemplate().search(transaction, values)
    handler = SearchHandler('email', form)
    handler.args = (
        'name', 'description', 'category'
    )
    handler.headers = (
        ('Name', 'name'), ('Description', 'description'),
        ('Categories', '')
    )

    def search_method(values, offset, orderby, orderby_dir):
        name, description, category = values

        search = transaction.get_email_domain_searcher()
        setup_searcher([search], orderby, orderby_dir, offset)

        if name:
            search.set_name_like(name)
        if description:
            search.set_description_like(description)
        if category:
            #TODO
            pass

        return search.search()

    def row(elm):
        link = object_link(elm)
        cats = [i.get_name() for i in elm.get_categories()[:4]]
        cats = ", ".join(cats[:3]) + (len(cats) == 4 and '...' or '')
        edit = object_link(elm, text='edit', method='edit', _class='actions')
        remb = remember_link(elm, _class='actions')
        return link, elm.get_description(), cats, str(edit)+str(remb)
    
    domains = handler.search(search_method, **vargs)
    result = handler.get_result(domains, row)
    page.content = lambda: result
    
    return page
search = transaction_decorator(search)
search.exposed = True

def create(transaction):
    page = Main()
    page.title = _("Email domains")
    page.setFocus("email/create")
    content = EmailDomainTemplate().create(transaction)
    page.content = lambda: content
    return page
create = transaction_decorator(create)
create.exposed = True

def categories(transaction):
    page = Main()
    page.title = _("Email domain categories")
    page.setFocus("email/categories")
    content = EmailDomainTemplate().categories(transaction)
    page.content = lambda: content
    return page
categories = transaction_decorator(categories)
categories.exposed = True

def view(transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main()
    page.title = _("Email domain %s") % domain.get_name()
    page.setFocus("email/view", id)
    template = EmailDomainTemplate()
    content = template.view_domain(transaction, domain)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def addresses(transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main()
    page.title = _("Addresses in ") + object_link(domain)
    page.setFocus("email/addresses", id)
    template = EmailDomainTemplate()
    content = template.list_addresses(transaction, domain)
    page.content = lambda: content
    return page
addresses = transaction_decorator(addresses)
addresses.exposed = True

def edit(transaction, id):
    domain = transaction.get_email_domain(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(domain)
    page.setFocus("email/edit", id)
    template = EmailDomainTemplate()
    content = template.edit_domain(domain)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, name, description, submit=None):
    domain = transaction.get_email_domain(int(id))

    if submit == "Cancel":
        redirect_object(domain)
        return

    domain.set_name(name)
    domain.set_description(description)

    commit(transaction, domain, msg=_('Email domain successfully updated.'))
save = transaction_decorator(save)
save.exposed = True

def make(transaction, name, description, category):
    msg=''
    if name:
        if not legal_domain_format(name):
            msg=_('Domain-name is not a legal name.')
        if not msg:
            if not legal_domain_chars(name):
                msg=_('Domain-name contains unlegal characters.')
    else:
        msg=_('Domain name is empty.')

    import_err=False
    mx_exists=False
    if not msg:
        try:
            sys.path.append('/home/kandal/python/dnspython-1.5.0')
            import dns.resolver
        except ImportError:
            import_err=True
        else:
            try:
                answers=dns.resolver.query( name, 'MX')
            except dns.resolver.NXDOMAIN:
                pass
            else:
                mx_exists=True
    
    if not msg and import_err:
        msg=_('DNS-library not installed. DNS-query cannot be executed.')
    if not msg and not mx_exists:
        msg=_('Domain-name is not registered in DNS.')

    if not msg:
        domain = transaction.get_commands().create_email_domain(name, description)
        if category:
            category = transaction.get_email_domain_category(category)
            domain.add_to_category(category)

        commit(transaction, domain, msg=_('Email domain successfully created.'))
    else:
        rollback_url('/email/create', msg, err=True)
make = transaction_decorator(make)
make.exposed = True

def delete(transaction, id):
    domain = transaction.get_email_domain(int(id))
    msg = _("Email domain '%s' successfully deleted.") % domain.get_name()
    domain.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

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

def make_target(transaction, entity, target_type, alias):
    entity = transaction.get_entity(int(entity))
    target_type = transaction.get_email_target_type(target_type)
    target = transaction.get_commands().create_email_target(target_type)
    target.set_entity(entity)
    
    if alias:
        target.set_alias(alias)
    if entity.get_type().get_name() == "account" and entity.is_posix():
        target.set_using(entity)
    
    msg = _("Added email target (%s) successfully.") % target_type.get_name()
    commit(transaction, entity, msg=msg)
make_target = transaction_decorator(make_target)
make_target.exposed = True

def remove_target(transaction, entity, target):
    entity = transaction.get_entity(int(entity))
    target = transaction.get_email_target(int(target))
    type = target.get_type().get_name()
    target.delete_email_target()
    msg = _("Removed email target (%s) successfully.") % type
    commit(transaction, entity, msg=msg)
remove_target = transaction_decorator(remove_target)
remove_target.exposed = True

# arch-tag: b3739600-040d-11da-97b3-692f6b35af14
