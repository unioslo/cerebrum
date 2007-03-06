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
    order = []
    fields = {}

    def __init__(self, transaction, **values):
        self.transaction = transaction
        for key, field in self.fields.items():
            value = values.get(key, None)
            field['value'] = value

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
            if field['cls'] == 'required' and not field['value']:
                res = False
                self.error_message = _("Required field '%s' is empty.") % field['label']
                break
        return res

    def is_correct(self):
        correct = True
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
    order = [
        'firstname',
        'lastname',
        'externalid',
        'gender',
        'birthdate',
        'description',
    ]
    fields = {
        'firstname': {
            'name': 'firstname',
            'label': _('First name'),
            'cls': 'required',
            'type': 'text',
        },
        'lastname': {
            'name': 'lastname',
            'label': _('Last name'),
            'cls': 'required',
            'type': 'text',
        },
        'gender': {
            'name': 'gender',
            'label': _('Gender'),
            'cls': 'required',
            'type': 'select',
        },
        'birthdate': {
            'name': 'birthdate',
            'label': _('Birth date'),
            'cls': 'required',
            'type': 'text',
        },
        'externalid': {
            'name': 'externalid',
            'label': _('Social Security Number'),
            'cls': 'required',
            'type': 'text',
        },
        'description': {
            'name': 'description',
            'label': _('Description'),
            'cls': 'optional',
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
