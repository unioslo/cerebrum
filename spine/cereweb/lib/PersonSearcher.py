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
from lib.forms import PersonSearchForm
from lib.data.PersonDAO import PersonDAO
from gettext import gettext as _

class PersonSearcher(CoreSearcher):
    url = ''
    DAO = PersonDAO
    SearchForm = PersonSearchForm

    headers = [
        (_('First name'), 'first_name'),
        (_('Last name'), 'last_name'),
        (_('Date of birth'), 'birth_date'),
        (_('Gender'), ''),
        (_('Account(s)'), ''),
    ]

    columns = (
        'first_name',
        'last_name',
        'birth_date',
        'gender',
        'accounts',
    )

    orderby_default = 'last_name'

    def _extend_limited_result(self, results):
        owner_ids = [r.id for r in results]

        accounts = self.dao.get_accounts(*owner_ids)
        account_map = {}
        for account in accounts:
            l = account_map.setdefault(account.owner_id, [])
            l.append(account)

        for r in results:
            r.accounts = account_map.get(r.id, [])

        return results

    format_first_name = CoreSearcher._create_link
    format_last_name = CoreSearcher._create_link
    format_birth_date = CoreSearcher._format_date

    def format_gender(self, gender, row):
        return str(gender) == "M" and _("Male") or _("Female")

    def format_accounts(self, accounts, row):
        links = []
        for account in accounts:
            link = self._create_link(account.name, account)
            links.append(link)
        return ", ".join(links) or "&nbsp;"
