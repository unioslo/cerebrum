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
    pass

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
