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
from lib.utils import get_database
from lib.data.ConstantsDAO import ConstantsDAO

class AffiliatedPersonSearchForm(SearchForm):
    def __init__(self, *args, **kwargs):
        super(AffiliatedPersonSearchForm, self).__init__(*args, **kwargs)

        db = get_database()
        self.dao = ConstantsDAO(db)

    title = _('Search for Affiliated Person')
    action = '/ou/perform_search'
    method = 'GET'

    Order = [
        'ou_id',
        'perspective_type',
        'affiliation_type',
        'recursive',
    ]

    Fields = {
        'ou_id': {
            'label': _('OU id'),
            'required': True,
            'type': 'hidden',
            'quote': 'reject',
        },
        'perspective_type': {
            'label': _('Perspective'),
            'required': True,
            'type': 'select',
            'quote': 'reject',
        },
        'affiliation_type': {
            'label': _('Affiliation'),
            'required': False,
            'type': 'select',
            'quote': 'reject',
        },
        'recursive': {
            'label': _('Recursive search'),
            'required': False,
            'type': 'checkbox',
            'quote': 'reject',
        },
    }

    def _constants_to_options(self, constants):
        return [(c.id, c.name) for c in constants]

    def get_affiliation_type_options(self):
        affiliations = self.dao.get_affiliation_types()
        options = self._constants_to_options(affiliations)
        options.insert(0, ("", " - Any affiliation - "))
        return options

    def get_perspective_type_options(self):
        perspectives = self.dao.get_ou_perspective_types()
        return self._constants_to_options(perspectives)
