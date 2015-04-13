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


from Cerebrum.modules.ad2.ADSync import UserSync
from Cerebrum.modules.ad2.CerebrumData import CerebrumUser, CerebrumGroup

class UiAUserSync(UserSync):

    """ Override of the Usersync, for UiA specific, complex behaviour. """

    def attribute_mismatch(self, ent, atr, c, a):
        """Compare an attribute between Cerebrum and AD, UiA-wize.

        This method ignores certain Exchange attributes if the user has the
        spread `account@exchange`. For anything else, `super` is doing the rest.

        This is a temporary hack, while waiting for the functionality in
        CRB-523. Users with the spread "account@exchange" will be provisioned
        through the new Exchange integration for Exchange 2013. The regular
        AD-sync updated attributes for Exchange 2010 (spread account@exch_old).
        The two Exchange versions are using some of the same AD attributes, but
        they're using them differently, which creates conflicts with the two
        syncs. The quick solution here is to ignore certain exchange attributes
        if the user has the new Exchange spread.

        """
        # List of the attributes that Exchange 2013 needs, and which we
        # therefore should ignore:
        exch2013attrs = ('homemdb', 'msexchhomeservername', 'mdbusedefaults',
                         'deliverandredirect', 'mdboverquotalimit',
                         'mdboverhardquotalimit', 'mdbstoragequota',
                         'proxyaddresses', 'targetaddress', 'homemta',
                         'legacyexchangedn', 'mail', 'msexchmailboxguid',
                         'msexchpoliciesexcluded', 'msexchpoliciesincluded',
                         'msexchuserculture',
                         )
        # Force not updating certain Exchange attributes when user has spread
        # for Exchange 2013 (which are updated through event_daemon):
        if (self.co.spread_exchange_account in ent.spreads and
                atr.lower() in exch2013attrs):
            self.logger.debug3('Ignoring Exchange 2013 attribute "%s" for %s',
                               atr, ent)
            return (False, None, None)
        # Also do some ignoring for Office 365 accounts
        if (self.co.spread_uia_office_365 in ent.spreads and
                atr.lower() in exch2013attrs):
            self.logger.debug3('Ignoring Office365 attribute "%s" for %s',
                               atr, ent)
            return (False, None, None)
        return super(UiAUserSync, self).attribute_mismatch(ent, atr, c, a)

class UiACerebrumUser(CerebrumUser):
    """UiA specific behaviour and attributes for a user object."""

    def calculate_ad_values(self):
        """Adding UiA specific attributes."""
        super(UiACerebrumUser, self).calculate_ad_values()

        # Hide all accounts that are not primary accounts:
        self.set_attribute('MsExchHideFromAddressLists',
                           not self.is_primary_account)


class UiACerebrumDistGroup(CerebrumGroup):
    """
    This class represent a virtual Cerebrum distribution group that
    contain contact objecs per user at UiA.
    """
    def __init__(self, logger, config, entity_id, entity_name,
                 description = None):
        """
        CerebrumDistGroup constructor

        """
        super(UiACerebrumDistGroup, self).__init__(logger, config, entity_id,
                                                   entity_name, description)

    def calculate_ad_values(self):
        """
        Calculate AD attrs from Cerebrum data.

        """
        super(UiACerebrumDistGroup, self).calculate_ad_values()
        self.set_attribute('Member', ["CN=" + y.ad_id + "," + y.ou
                                      for y in self.forwards_data['members']])

