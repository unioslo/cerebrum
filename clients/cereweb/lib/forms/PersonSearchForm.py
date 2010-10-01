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
from lib.forms.FormBase import SearchForm

class PersonSearchForm(SearchForm):
    title = _('Search for Person')
    action = '/person/search/'

    Order = [
        'name',
        'first_name',
        'last_name',
        'birth_date',
    ]

    Fields = {
        'name': {
            'label': _('Name'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'first_name': {
            'label': _('First name'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'last_name': {
            'label': _('Last name'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'birth_date': {
            'label': _('Birth date'),
            'required': False,
            'type': 'text',
            'help': _('Date must be in YYYY-MM-DD'),
        },
    }

    check_birth_date = SearchForm._check_date

    def check(self):
        values = self.get_values()

        name = values.get('name')
        first_name = values.get('first_name')
        last_name = values.get('last_name')
        birth_date = values.get('birth_date')

        is_valid = self._is_not_empty(name) or \
            self._is_not_empty(first_name) or \
            self._is_not_empty(last_name) or \
            self._is_not_empty(birth_date)
        if not is_valid:
            self.error_message = _("Search form can't be empty.")

        return is_valid

    def _is_not_empty(self, value):
        val = value.strip()
        if not val:
            return False

        if not val.strip('*'):
            return False

        return True

    help = [
        _('Use wildcards * and ? to extend the search.'),
    ]
