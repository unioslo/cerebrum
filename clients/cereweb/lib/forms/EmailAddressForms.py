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

import operator
from gettext import gettext as _
from lib.forms.FormBase import CreateForm, EditForm

from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.EmailAddressDAO import EmailAddressDAO
from lib.data.EmailDomainDAO import EmailDomainDAO
from lib.utils import entity_link, get_database, spine_to_web
from lib.utils import legal_date, legal_emailname

class EmailAddressCreateForm(CreateForm):
    action = '/emailaddress/create/'
    title = _('Add a new email address')
    form_class = "info box"

    Order = [
        'target_id',
        'local',
        'domain',
        'expire',
    ]

    Fields = {
        'target_id': {
            'label': _("Target ID"),
            'type': 'hidden',
            'required': True,
        },
        'local': {
            'label': _("Local part"),
            'type': 'text',
            'required': True,
            'quote': 'reject',
        },
        'domain': {
            'label': _("Domain"),
            'type': 'select',
            'required': True,
        },
        'expire': {
            'label': _("Expire date"),
            'type': 'text',
            'required': False,
            'help': _("Date format must be YYYY-MM-DD"),
        },
    }

    def __init__(self, target_id, *args, **kwargs):
        super(EmailAddressCreateForm, self).__init__(*args, **kwargs)
        self.set_value('target_id', target_id)
        self.db = get_database()

    def get_domain_options(self):
        domain_dao = EmailDomainDAO(self.db)
        domains =  [(d.id, d.name.lower()) for d in domain_dao.search()]
        return sorted(domains, key=operator.itemgetter(1))

    def check_local(self, local_name):
        """
        Validates the local name and returns None if valid, else
        the error message that should be displayed.
        """
        if not local_name:
            self.error_message = _('Local is empty.')
            return False

        if not legal_emailname(local_name):
            self.error_message = _('Local is not a legal name.')
            return False

        return True

    def check_expire(self, expire_date):
        """
        Validates the expire date and returns None if valid, else
        the error message that should be displayed.
        """
        if expire_date and not legal_date(expire_date):
            self.error_message = _('Expire date is not a legal date.')
            return False
        return True

    def check(self):
        return self.is_postback()

class EmailAddressEditForm(EditForm, EmailAddressCreateForm):
    action = '/emailaddress/edit/'
    form_class = "info box"
    title = _("Edit email address")

    Order = [
        'address_id',
        'target_id',
        'local',
        'domain',
        'expire',
    ]

    Fields = {
        'target_id': {
            'label': _("Target ID"),
            'type': 'hidden',
            'required': True,
        },
        'address_id': {
            'label': _("Address ID"),
            'type': 'hidden',
            'required': True,
        },
        'local': {
            'label': _("Local part"),
            'type': 'text',
            'required': True,
            'quote': 'reject',
        },
        'domain': {
            'label': _("Domain"),
            'type': 'select',
            'required': True,
        },
        'expire': {
            'label': _("Expire date"),
            'type': 'text',
            'required': False,
            'help': _("Date format must be YYYY-MM-DD"),
        },
    }

    def __init__(self, address_id, *args, **kwargs):
        super(EmailAddressEditForm, self).__init__(*args, **kwargs)
        self.set_value('address_id', address_id)

        self.db = get_database()
        if not self.is_postback():
            emailaddress = EmailAddressDAO(self.db).get(address_id)
            self.update_values({
                'local': emailaddress.local,
                'domain': emailaddress.domain.id,
                'expire': emailaddress.expire,
            })

    def check(self):
        return self.is_postback()
