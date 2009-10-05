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

from lib.Searchers import CoreSearcher
from lib.forms import AccountSearchForm
from lib.data.AccountDAO import AccountDAO
from lib.data.EntityFactory import EntityFactory
from gettext import gettext as _

class AccountSearcher(CoreSearcher):
    url = ''
    DAO = AccountDAO
    SearchForm = AccountSearchForm

    columns = (
        'name',
        'owner.name',
    )

    headers = [
            (_('Name'), 'name'),
            (_('Owner'), 'owner.name'),
        ]

    orderby_default = 'name'

    def _add_owners(self, results):
        factory = EntityFactory(self.db)
        for result in results:
            result.owner = factory.get_entity(result.owner_id, result.owner_type)
        return results

    def _extend_complete_results(self, results):
        return self._add_owners(results)

    def format_name(self, column, row):
        return self._create_link(column, row)

    def format_owner_name(self, column, row):
        return self._create_link(column, row.owner)
