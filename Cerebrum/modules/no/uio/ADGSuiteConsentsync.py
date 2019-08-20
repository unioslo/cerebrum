#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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

"""GSuite specific account selection criterias.

We only provision primary accounts for GSuite."""

from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.ad2.froupsync import _FroupSync


class GSuiteConsentGroupSync(_FroupSync):

    @memoize
    def pe2accs(self, person_id):
        """ Fetch the primary account for a person.

        :param int person_id: The entity ID of an *existing* person entity.

        :return list:
            TODO: Tuples of (account_name, has_ad_spread),

        """
        accs = []

        for acc in self.ac.list_accounts_by_type(person_id=person_id,
                                                 primary_only=True):
            self.ac.clear()
            self.ac.find(acc['account_id'])
            accs.append(
                (self.ac.account_name,
                 self.is_ad_account(self.ac)))
        return accs
