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
from lib.GroupSearchForm import GroupSearchForm
from lib.data.GroupDAO import GroupDAO
from gettext import gettext as _

class GroupSearcher(CoreSearcher):
    url = ''
    DAO = GroupDAO
    SearchForm = GroupSearchForm

    columns = (
        'name',
        'description',
    )

    headers = (
        (_('Group name'), 'name'),
        (_('Description'), 'description'),
    )

    orderby_default = 'name'

    def format_name(self, column, row):
        return self._create_link(column, row)
