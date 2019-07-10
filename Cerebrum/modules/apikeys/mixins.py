# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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
"""
Mixins related to mod_apikeys.
"""
from Cerebrum.Account import Account
from .dbal import ApiKeys


class ApiKeyMixin(Account):
    """
    Account mixin class that provides api key cleanup.
    """

    def delete(self):
        """Delete any account apikeys."""
        # Delete any existing API key if account is deleted.
        keys = ApiKeys(self._db)
        for row in keys.search(account_id=self.entity_id):
            keys.delete(row['account_id'], row['label'])
        super(ApiKeyMixin, self).delete()
