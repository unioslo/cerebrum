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

class EmailDomainSearchForm(SearchForm):
    title = _("Email domain search")
    action = '/email/search/'

    Order = [
        'name',
        'category',
        'description',
    ]

    Fields = {
        'name': {
            'label': _("Name"),
            'required': False,
            'type': 'text',
        },
        'category': {
            'label': _("Category"),
            'required': False,
            'type': 'select',
        },
        'description': {
            'label': _("Description"),
            'required': False,
            'type': 'text',
        },
    }

    check_path = SearchForm._check_short_string

    def get_category_options(self):
        db = get_database()
        dao = ConstantsDAO(db)
        domain_categories = dao.get_email_domain_categories()
        categories = [(d.id, d.name) for d in domain_categories]
        categories.insert(0, ("", _(" - All categories - ")))
        return categories

    def check(self):
        """
        Don't search unless we've got search text.
        """
        return self.is_postback()

    help = [
        _('Use wildcards * and ? to extend the search.'),
    ]
