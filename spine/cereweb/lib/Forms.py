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

"""
Helper-module for search-pages and search-result-pages in cereweb.
"""

class Form(object):
    order = []
    fields = {}
    def __init__(self, transaction, **values):
        for key, field in self.fields.items():
            value = values.get(key, None)
            field['value'] = value
            if field['type'] == 'select':
                field['options'] = values.get('%s_options' % key, None)

    def has_required(self):
        res = True
        for field in self.fields.values():
            if field['cls'] == 'required' and not field['value']:
                res = False
                self.error_message = _("Required field '%s' is empty.") % field['label']
                break
        return res

    def get_fields(self):
        res = []
        for key in self.order:
            res.append(self.fields[key])
        return res

    def get_error_message(self):
        message = getattr(self, 'error_message', '')
        return message and (message, True) or False

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
