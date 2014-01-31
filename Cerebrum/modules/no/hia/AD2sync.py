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

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailTarget, EmailQuota

from Cerebrum.modules.ad2.ADSync import UserSync, GroupSync
from Cerebrum.modules.ad2.CerebrumData import CerebrumUser, CerebrumGroup

class UiAUserSync(UserSync):
    """UiA specific behaviour for the sync of users."""
    def attribute_mismatch(self, ent, atr, c, a):
        """Compare an attribute between Cerebrum and AD.

        Overridden to handle special attributes for UiA.

        The ProxyAddresses attribute is also updated by Office365, with
        addresses starting with x500. We should ignore such attributes when
        comparing, to avoid having to update 20000 objects at each run. We
        should only take care of SMTP addresses.

        TODO: We should rather have this configurable and reusable for other
        instances, as these problems will probably exist for others too.

        """
        if atr.lower() == 'proxyaddresses' and c and a:
            advalues = list(sorted(v for v in a if not v.startswith('x500:')))
            cevalues = list(sorted(c))
            match = cevalues != advalues
            # TODO: remove logging when done debugging
            self.logger.debug2("Proxy: match=%s", match)
            self.logger.debug2("    AD: %s", advalues)
            self.logger.debug2("    C:  %s", cevalues)
            return match
        return super(UiAUserSync, self).attribute_mismatch(ent, atr, c, a)

class UiACerebrumUser(CerebrumUser):
    """UiA specific behaviour and attributes for a user object."""

    def calculate_ad_values(self):
        """Adding UiA specific attributes."""
        super(UiACerebrumUser, self).calculate_ad_values()
        co = Factory.get('Constants')(Factory.get('Database'))
        has_exchange = co.spread_exchange_account in self.spreads

        # Hide all accounts that are not primary accounts:
        self.set_attribute('MsExchHideFromAddressLists',
                           not self.is_primary_account)
