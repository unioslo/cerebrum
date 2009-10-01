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

from lib.data.EntityFactory import EntityFactory
from lib.PersonSearcher import PersonSearcher
from lib.forms import AffiliatedPersonSearchForm
from gettext import gettext as _

class AffiliatedPersonSearcher(PersonSearcher):
    search_method = 'search_affiliated'
    SearchForm = AffiliatedPersonSearchForm

    headers = [
        (_('First name'), 'first_name'),
        (_('Last name'), 'last_name'),
        (_('Date of birth'), 'birth_date'),
        (_('Gender'), ''),
        (_('Account(s)'), ''),
        (_('Affiliation'), ''),
    ]

    columns = (
        'first_name',
        'last_name',
        'birth_date',
        'gender',
        'accounts',
        'status',
    )

    def format_status(self, status, row):
        return str(status)
