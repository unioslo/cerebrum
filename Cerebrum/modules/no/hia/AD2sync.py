#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2013 University of Oslo, Norway
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
"""AD sync functionality specific to UiA.

The (new) AD sync is supposed to be able to support most of the functionality
that is required for the different instances. There are still, however,
functionality that could not be implemented generically, and is therefore put
here.

Note: You should put as little as possible in subclasses of the AD sync, as it
then gets harder and harder to improve the code without too much extra work by
testing all the subclasses.

"""

import cerebrum_path
import cereconf

from Cerebrum.modules.Email import EmailTarget, EmailQuota

from Cerebrum.modules.ad2.ADSync import UserSync, GroupSync
from Cerebrum.modules.ad2.CerebrumData import CerebrumUser, CerebrumGroup

class UiAUserSync(UserSync):
    """UiA specific behaviour for the sync of users."""

    def fetch_cerebrum_data(self):
        """Fetch Cerebrum data specific for UiA."""
        super(UiAUserSync, self).fetch_cerebrum_data()

        # Find out who has the exchange spread, if defined:
        # TODO: need a config variable for this:
        if self.config.get('exchange_spread'):
            for row in self.ac.search(spread=self.config['exchange_spread']):
                self.entities.get(row['account_id'])
                if ent:
                    ent.spread_to_exchange = True

        for row in self.ac.list_traits(self.co.trait_exchange_mdb):
            ent = self.id2entity.get(row['entity_id'])
            if ent:
                ent.homeMDB = row['strval']

        # TODO:

class UiACerebrumUser(CerebrumUser):
    """UiA specific behaviour and attributes for a user object."""

    def calculate_ad_values(self):
        """Adding UiA specific attributes."""
        super(UiACerebrumUser, self).calculate_ad_values()

        # ipPhone: SIP phones - only last 4 digits in phone numbers, if the
        # phone number is in a defined SIP serie:
        tlf = self.attributes.get('TelephoneNumber')
        if tlf and any(tlf.startswith(pre) for pre in ('37233', '38141',
                                                       '38142')):
            self.set_attribute('ipPhone', tlf[-4:])

        self.set_attribute('deliverAndRedirect',
                           cereconf.AD_DELIVER_AND_REDIRECT)

        # If no Exchange-spread, we're done
        if not self.spread_to_exchange:
            return

        self.set_attribute("MsExchPoliciesExcluded",
                           "{26491cfc-9e50-4857-861b-0cb8df22b5d7}")
        if hasattr(self, 'homeMDB'):
            self.set_attribute('MsExchHomeServerName',
                               cereconf.AD_EX_HOME_SERVER)
            self.set_attribute('HomeMDB', "CN=%s,%s" % (self.homeMDB,
                                                        cereconf.AD_EX_HOME_MDB))

        # Hide all accounts that are not primary accounts:
        self.set_attribute('msExchHideFromAddressLists',
                           not self.maildata['is_primary_account'])

