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

from gettext import gettext as _
from lib.forms.FormBase import Form
from lib.forms.FormBase import SearchForm

from lib.data.AccountDAO import AccountDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.utils import randpasswd, entity_link, get_database

class AccountCreateForm(Form):
    def __init__(self, transaction, **values):
        self.transaction = transaction
        super(AccountCreateForm, self).__init__(**values)

    action = '/account/create'

    Order = [
        'owner_id',
        'name',
        '_other',
        'group',
        'expire_date',
        'password0',
        'password1',
        'randpasswd',
    ]

    Fields = {
        'owner_id': {
            'required': True,
            'type': 'hidden',
            'label': _('Owner id'),
        },
        'name': {
            'label': _('Select username'),
            'required': True,
            'type': 'select',
        },
        '_other': {
            'label': _('Enter username'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'expire_date': {
            'label': _('Expire date'),
            'required': False,
            'type': 'text',
            'help': _('Date must be in YYYY-MM-DD format.'),
        },
        'group': {
            'label': _('Primary group'),
            'required': False,
            'cls': 'ac_group',
            'type': 'text',
            'quote': 'reject',
        },
        'password0': {
            'label': _('Enter password'),
            'required': False,
            'type': 'password',
        },
        'password1': {
            'label': _('Re-type password'),
            'required': False,
            'type': 'password',
        },
        'randpasswd': {
            'label': _('Random password'),
            'required': False,
            'type': 'radio',
            'name': 'randpwd',
            'value': [randpasswd() for i in range(10)],
        },
    }

    def init_form(self):
        self.owner = self.values.get("owner_entity")
        self.type = self.owner.type_name
        self.name = self.owner.name

    def get_name_options(self):
        db = get_database()
        usernames = AccountDAO(db).suggest_usernames(self.owner)
        return [(username, username) for username in usernames]

    def get_title(self):
        return "%s %s" % (_('Owner is'), entity_link(self.owner))

    check_expire_date = Form._check_date

    def check(self):
        pwd0 = self.fields['password0'].get('value', '')
        pwd1 = self.fields['password1'].get('value', '')
            
        if (pwd0 and pwd1) and (pwd0 == pwd1) and (len(pwd0) < 8):
            self.error_message = 'The password must be 8 chars long.'
            return False

        msg = 'The two passwords differ.'
        if (pwd0 and pwd1) and (pwd0 != pwd1):
            self.error_message = msg
            return False

        if (pwd0 and not pwd1) or (not pwd0 and pwd1):
            self.error_message = msg
            return False

        return True

class NonPersonalAccountCreateForm(AccountCreateForm):
    Fields = AccountCreateForm.Fields.copy()
    Fields['np_type'] = {
        'label': _('Account type'),
        'required': True,
        'type': 'select',
    }
    Fields['join'] = {
        'label': _('Join %s'),
        'type': 'checkbox',
        'required': False,
    }

    def init_form(self):
        fields['join']['label'] = fields['join']['label'] % self.name

    Order = AccountCreateForm.Order[:]
    Order.append('np_type')
    Order.append('join')
        
    def get_np_type_options(self):
        db = get_database()
        account_types = ConstantsDAO(db).get_account_types()
        return [(t.id, t.description) for t in account_types]
