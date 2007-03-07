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
from lib.utils import legal_date

"""
Helper-module for search-pages and search-result-pages in cereweb.
"""

class Form(object):
    def __init__(self, transaction, **values):
        self.values = values
        self.transaction = transaction

        self.init_form()

        for key, field in self.fields.items():
            value = self.values.get(key, None)
            field['name'] = key
            field['value'] = value

    def init_form(self):
        self.order = []
        self.fields = {}

    def get_fields(self):
        res = []
        for key in self.order:
            field = self.fields[key]
            if field['type'] == 'select':
                func = getattr(self, 'get_%s_options' % key)
                field['options'] = func()
            res.append(field)
        return res

    def has_required(self):
        res = True
        for field in self.fields.values():
            if field['required'] and not field['value']:
                res = False
                self.error_message = _("Required field '%s' is empty.") % field['label']
                break
        return res

    def is_correct(self):
        correct = self.has_required()
        if correct:
            for field in self.fields.values():
                if field['value']:
                    func = getattr(self, field['name'], None)
                    if func and not func(field['value']):
                        correct = False
                        message = "Field '%s' " % field['label']
                        self.error_message = message + self.error_message
                        break
        return correct

    def get_error_message(self):
        message = getattr(self, 'error_message', False)
        return message and (message, True) or ''

    def _short_string(self, name):
        is_correct = True
        if len(name) > 256:
            is_correct = False
            self.error_message = 'too long (max. 256 characters).'
        return is_correct
            
class PersonCreateForm(Form):
    def init_form(self):
        self.order = [
            'firstname',
            'lastname',
            'externalid',
            'gender',
            'birthdate',
            'description',
        ]
        self.fields = {
            'firstname': {
                'label': _('First name'),
                'required': True,
                'type': 'text',
            },
            'lastname': {
                'label': _('Last name'),
                'required': True,
                'type': 'text',
            },
            'gender': {
                'label': _('Gender'),
                'required': True,
                'type': 'select',
            },
            'birthdate': {
                'label': _('Birth date'),
                'required': True,
                'type': 'text',
                'help': _('Date must be in YYYY-MM-DD format.'),
            },
            'externalid': {
                'label': _('Social Security Number'),
                'required': True,
                'type': 'text',
            },
            'description': {
                'label': _('Description'),
                'required': False,
                'type': 'text',
            }
        }

    def get_gender_options(self):
        return [(g.get_name(), g.get_description()) for g in 
                   self.transaction.get_gender_type_searcher().search()]

    def firstname(self, name):
        return self._short_string(name)

    def lastname(self, name):
        return self._short_string(name)

    def birthdate(self, date):
        is_correct = True
        if not legal_date(date):
            self.error_message = 'not a legal date.'
            is_correct = False
        return is_correct

class PersonEditForm(PersonCreateForm):
    def init_form(self):
        self.order = [
            'id', 'gender', 'birthdate', 'description', 'deceased'
        ]
        self.fields = {
            'id': {
                'label': 'id',
                'required': True,
                'type': 'hidden',
            },
            'gender': {
                'label': _('Gender'),
                'required': True,
                'type': 'select',
            },
            'birthdate': {
                'label': _('Birth date'),
                'required': True,
                'type': 'text',
                'help': 'YYYY-MM-DD',
            },
            'description': {
                'label': _('Description'),
                'required': False,
                'type': 'text',
            },
            'deceased': {
                'label': _('Deceased date'),
                'required': True,
                'type': 'text',
                'help': 'YYYY-MM-DD',
            },
        }

    def deceased(self, date):
        is_correct = True
        if not legal_date(date):
            self.error_message = 'not a legal date.'
            is_correct = False
        return is_correct

class AccountCreateForm(Form):
    def init_form(self):
        self.order = [
            'owner', 'name', '_other', 'group', 'expiredate'
        ]
        self.fields = {
            'owner': {
                'required': True,
                'type': 'hidden',
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
            },
            'expiredate': {
                'label': _('Expire date'),
                'required': True,
                'type': 'text',
                'help': _('Date must be in YYYY-MM-DD format.'),
            },
            'group': {
                'label': _('Primary group'),
                'required': True,
                'cls': 'ac_group',
                'type': 'text',
            }
        }

        owner = self.transaction.get_entity(int(self.values.get('owner')))

        if owner.get_type().get_name() == 'person':
            self.type = 'person'
            self.name = owner.get_cached_full_name()
        else:
            self.type = owner.get_type()
            self.name = owner.get_name()
            self.fields['np_type'] = {
                'label': _('Account type'),
                'required': True,
                'type': 'select',
            }
            self.fields['join'] = {
                'label': _('Join %s') % self.name,
                'type': 'checkbox',
                'required': False,
            }
            self.order.append('np_type')
            self.order.append('join')

    def get_name_options(self):
        names = self.name.split(' ')
        if len(names) == 1:
            first = ''
            last = names[0]
        else:
            first = names[0]
            last = names[-1]

        usernames = self.transaction.get_commands().suggest_usernames(first, last)
        return [(username, username) for username in usernames]

    def get_np_type_options(self):
        searcher = self.transaction.get_account_type_searcher()
        return [(t.get_name(), t.get_description()) for t in searcher.search()]

    def get_title(self):
        return "%s %s" % (_('Owner is'), self.name)
