# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import socket
from gettext import gettext as _
from lib.forms.FormBase import CreateForm, EditForm

from lib.data.EmailDomainDAO import EmailDomainDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.utils import entity_link, get_database, spine_to_web
from lib.utils import legal_domain_chars, legal_domain_format

class EmailDomainCreateForm(CreateForm):
    action = '/email/create/'

    Order = [
        'name',
        'description',
        'category',
    ]

    Fields = {
        'name': {
            'label': _('Domain name'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'description': {
            'label': _('Description'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'category': {
            'label': _('Category'),
            'required': False,
            'type': 'select',
        },
    }

    def get_title(self):
        return _('Create a new email domain')

    def check_name(self, name):
        if not name:
            self.error_message = _('Domain name is empty.')
            return False

        if not legal_domain_format(name):
            self.error_message = _('Domain-name is not a legal name.')
            return False

        if not legal_domain_chars(name):
            self.error_message = _('Domain-name contains unlegal characters.')
            return False

        if not self.configured_domain(name):
            self.error_message = _('Domain-name is not registered in DNS.')
            return False

        return True

    def configured_domain(self, name):
        # We should really look up the MX here, but there is no module
        # in stdlib that does this.  Won't bring in an extra dependency
        # at this time so for now we just verify that the domain has an ip.
        try:
            socket.gethostbyname(name)
        except socket.gaierror:
            return False
        return True

    def get_category_options(self):
        db = get_database()
        categories = [(c.id, spine_to_web("%s: %s" % (c.name, c.description))) for c in
            ConstantsDAO(db).get_email_domain_categories()]
        categories.insert(0, ("", _("No Category")))
        return categories

class EmailDomainEditForm(EditForm, EmailDomainCreateForm):
    def __init__(self, id, *args, **kwargs):
        super(EmailDomainCreateForm, self).__init__(*args, **kwargs)

        self.db = get_database()
        self.email = EmailDomainDAO(self.db).get(id)

        values = self.get_values()
        values.update({'id': self.email.id})

        if not self.is_postback():
            values.update({
                'name': self.email.name,
                'description': self.email.description,
                'category': self.email.category,
            })

        self.set_values(values)

    action = '/email/edit/'

    Order = [
        'id',
        'name',
        'description',
        'category',
    ]

    Fields = {
        'id': {
            'label': _("Email domain ID"),
            'type': 'hidden',
            'required': True,
        },
        'name': {
            'label': _('Path'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'description': {
            'label': _('Description'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'category': {
            'label': _('Category'),
            'required': False,
            'type': 'select',
        },
    }

    def get_title(self):
        return _('Edit %s:') % entity_link(self.email)

    def check(self):
        return self.is_postback()
