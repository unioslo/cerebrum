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
from lib.utils import randpasswd, entity_link, get_database, date_in_the_future

class AccountCreateForm(Form):
    action = '/account/create/'

    Order = [
        'owner_id',
        'name',
        '_other',
        'group',
        'expire_date',
        'password0',
        'password1',
        'randpwd',
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
            'help' : _("Legal chars are [a-zA-Z0-9]. First char must be a letter.  Max. length 8."),
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
        'randpwd': {
            'label': _('Random password'),
            'required': False,
            'type': 'radio',
        },
    }
    
    def init_values(self, owner, *args, **kwargs):
        self.owner = owner
        self.set_value('owner_id', owner.id)
        self.set_value('randpwd', [randpasswd() for i in range(10)]),
        if self.get_value("expire_date") is None:
            self.set_value("expire_date", date_in_the_future(years=1))

        self._random_password = kwargs.get('randpwd')
            

    def get_name_options(self):
        db = get_database()
        usernames = AccountDAO(db).suggest_usernames(self.owner)
        return [(username, username) for username in usernames]

    def get_title(self):
        return "%s %s" % (_('Owner is'), entity_link(self.owner))

    check_expire_date = Form._check_date

    def check(self):
        pwd0 = self.get_value('password0')
        pwd1 = self.get_value('password1')

        if not (pwd0 or pwd1):
            pwd0 = pwd1 = self._random_password
            self.set_value('password0', pwd0)

        if not pwd0 == pwd1:
            self.error_message = 'The two passwords differ.'
            return False

        if len(pwd0) != 8:
            self.error_message = 'The password must be 8 chars long.'
            return False

        return True

class NonPersonalAccountCreateForm(AccountCreateForm):
    def init_fields(self, owner, *args, **kwargs):
        self.fields['np_type'] = {
            'label': _('Account type'),
            'required': True,
            'type': 'select',
        }
        self.order.append('np_type')

        self.fields['join'] = {
            'label': _('Join %s') % owner.name,
            'type': 'checkbox',
            'required': False,
        }
        self.order.append('join')

    def get_np_type_options(self):
        db = get_database()
        account_types = ConstantsDAO(db).get_account_types()
        return [(t.id, t.description) for t in account_types]
