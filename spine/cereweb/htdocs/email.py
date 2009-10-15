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

from gettext import gettext as _
from lib.utils import queue_message, redirect
from lib.utils import session_required_decorator
from lib.utils import web_to_spine, get_database
from lib.utils import redirect_entity
from lib.data.EmailDomainDAO import EmailDomainDAO
from lib.data.EmailAddressDAO import EmailAddressDAO
from lib.EmailDomainSearcher import EmailDomainSearcher
from lib.forms import EmailDomainCreateForm, EmailDomainEditForm
from lib.templates.EmailDomainTemplate import EmailDomainTemplate

@session_required_decorator
def search(**vargs):
    searcher = EmailDomainSearcher(**vargs)
    return searcher.respond()
search.exposed = True
index = search

@session_required_decorator
def create(**kwargs):
    """Creates a page with the form for creating a disk."""
    form = EmailDomainCreateForm(**kwargs)
    if form.is_correct():
        return make(**form.get_values())
    return form.respond()
create.exposed = True

@session_required_decorator
def edit(**kwargs):
    """Creates a page with the form for creating a disk."""
    form = EmailDomainEditForm(**kwargs)
    if form.is_correct():
        return save(**form.get_values())
    return form.respond()
edit.exposed = True

def make(name, description, category):
    domain_name = web_to_spine(name.strip())
    desc = web_to_spine(description.strip())

    db = get_database()
    dao = EmailDomainDAO(db)
    domain = dao.create(domain_name, desc)
    dao.set_category(domain.id, category)
    db.commit()

    queue_message(_("Email domain successfully created."), title=_("Change succeeded"))
    redirect_entity(domain)

def save(id, name, description, category):
    db = get_database()
    dao = EmailDomainDAO(db)
    dao.save(id, name, description)
    dao.set_category(id, category)
    db.commit()

    queue_message(_('Email domain successfully updated.'), title=_("Change succeded"))
    redirect_entity(id)

@session_required_decorator
def delete(id):
    db = get_database()
    dao = EmailDomainDAO(db)
    dao.delete(id)
    db.commit()

    queue_message(_('Email domain successfully deleted.'), title=_("Change succeded"))
    redirect('/email/')
delete.exposed = True

def view(id, view_all_addresses=None):
    db = get_database()

    page = EmailDomainTemplate()
    page.domain = EmailDomainDAO(db).get(id)
    page.addresses = EmailAddressDAO(db).search(domain_id=id)

    if view_all_addresses:
        page.max_addresses = "unlimited"

    return page.respond()
view.exposed = True
