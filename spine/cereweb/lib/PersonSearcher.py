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
from lib.PersonSearchForm import PersonSearchForm
from lib.data.PersonDAO import PersonDAO
from gettext import gettext as _

class PersonSearcher(CoreSearcher):
    url = ''
    DAO = PersonDAO
    SearchForm = PersonSearchForm

    columns = (
        'first_name',
        'last_name',
        'birth_date',
        'gender',
        'accounts',
    )

    headers = [
        ('First name', 'first_name'),
        ('Last name', 'last_name'),
        ('Date of birth', 'birth_date'),
        ('Gender', ''),
        ('Account(s)', ''),
    ]

    defaults = CoreSearcher.defaults.copy()
    defaults.update({
        'orderby': 'last_name',
    })


    def _get_results(self):
        if not hasattr(self, '__results'):
            name = (self.form_values.get('name') or '').strip()
            birth_date = (self.form_values.get('birth_date') or '').strip()

            self.__results = self.dao.search(
                name,
                birth_date,
                orderby=self.orderby,
                orderby_dir=self.orderby_dir)
        return self.__results

    def _extend_search_result(self, results):
        owner_ids = [r.id for r in results]

        accounts = self.dao.get_accounts(*owner_ids)
        account_map = {}
        for account in accounts:
            l = account_map.setdefault(account.owner_id, [])
            l.append(account)

        for r in results:
            r.accounts = account_map.get(r.id, [])

        return results

    def _create_view_link(self, entity, name, row):
        target_id = row.id
        return '<a href="/%s/view?id=%s">%s</a>' % (entity, target_id, name)

    def _create_person_link(self, name, row):
        return self._create_view_link("person", name, row)

    def _create_account_link(self, name, row):
        return self._create_view_link("account", name, row)

    format_first_name = _create_person_link
    format_last_name = _create_person_link
    format_birth_date = CoreSearcher._format_date

    def format_gender(self, gender, row):
        return str(gender) == "M" and _("Male") or _("Female")

    def format_accounts(self, accounts, row):
        links = []
        for account in accounts:
            link = self._create_account_link(account.name, account)
            links.append(link)
        return ", ".join(links) or "&nbsp;"
