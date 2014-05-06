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
import adconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailTarget, EmailQuota

from Cerebrum.modules.ad2.ADSync import BaseSync, UserSync, GroupSync
from Cerebrum.modules.ad2.CerebrumData import CerebrumUser, CerebrumGroup
from Cerebrum.modules import Email

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
                                      for y in self.ad_data['members']])


class UiADistGroupSync(BaseSync):
    """Sync for Cerebrum distribution groups in AD for UiA.

    """

    default_ad_object_class = 'group'


    def __init__(self, forward_objects, *args, **kwargs):
        """Instantiate forward addresses specific functionality."""
        super(UiADistGroupSync, self).__init__(*args, **kwargs)
        self.forwards = forward_objects


    def fetch_cerebrum_entities(self):
        """Create distribution groups out of forward addresses information
        to compare them against AD. The forward addresses are received upon
        class' initialization.
        
        """
        self.logger.debug("Making distribution groups")
        
        for key, value in self.forwards.iteritems():
            name, addr, ent_id = key.split(',')
            if name in self.entities:
                # Add the forward-object to the group
                self.entities[name].ad_data['members'].append(value)
            else:
                self.entities[name] = self.cache_entity(ent_id, name, 
                    description = 'Samlegruppe for brukerens forwardadresser')
                self.entities[name].ad_data['members'] = [value,]

