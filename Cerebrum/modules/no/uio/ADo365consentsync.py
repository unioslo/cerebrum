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

"""Office 365 specific account selection criterias.

We only provision primary accounts for Office365.

Configuration:
--------------
Extends the configuration with the following options:

grace_period
    Grace period for affiliations.

"""

import mx.DateTime

from Cerebrum.modules.ad2.froupsync import _FroupSync
from Cerebrum.utils.funcwrap import memoize


class O365ConsentGroupSync(_FroupSync):
    def configure(self, config_args):
        """Override the base configuration with O365 specific config

        :param dict config_args: configuration
        """
        super(O365ConsentGroupSync, self).configure(config_args)
        self.config['grace_period'] = config_args.get('grace_period', 0)

    @memoize
    def pe2affs(self, person_id):
        """ Get affiliations for a person.

        Set the affiliations enabled for deleted affiliations as well, as long
        as they are within the grace period.

        :param int person_id: The entity ID of an *existing* person entity.

        :return list:
            Tuples of (source system, affiliation type) for a given person.

        """

        self.pe.clear()
        self.pe.find(person_id)
        too_old = mx.DateTime.now() - self.config['grace_period']
        affs = [(row['source_system'], row['affiliation'])
                for row in self.pe.get_affiliations(include_deleted=True) if
                not row['deleted_date'] or row['deleted_date'] > too_old]
        return affs

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
