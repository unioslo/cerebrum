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

class UiAUserSync(UserSync):

    def configure(self, config_args):
        """Override the configuration for setting specific variables for UiA
        user sync.

        """
        super(UiAUserSync, self).configure(config_args)

        if 'forward_sync' in config_args:
            self.config['forward_sync'] = config_args['forward_sync']
        if 'distgroup_sync' in config_args:
            self.config['distgroup_sync'] = config_args['distgroup_sync']


    def fullsync(self):
        """Usually fullsync method is never subclassed. But for UiA there is
        a need to do it because usersync is tightly connected with sync of
        forward-addresses and distribution groups. All 3 syncs share information
        and depend on each other. So UserSync for UiA now triggers ForwardSync
        and DistGroupSync from inside itself, if the two latter are present
        in the configuration.

        """
        super(UiAUserSync, self).fullsync()
        if self.config.has_key('forward_sync'):
            self.logger.debug("Running forward sync")
            forward_sync_class = self.get_class(
                                     sync_type = self.config['forward_sync'])
            forward_sync = forward_sync_class(self.entities,
                                              self.db, self.logger)
            forward_conf = adconf.SYNCS[self.config['sync_type']].copy()
            for k, v in adconf.SYNCS[self.config['forward_sync']].iteritems():
                forward_conf[k] = v
            forward_conf['sync_type'] = self.config['sync_type']
            forward_sync.configure(forward_conf)
            forward_sync.fullsync()
        if self.config.has_key('distgroup_sync'):
            self.logger.debug("Running distribution groups sync")
            distgroup_sync_class = self.get_class(
                                     sync_type = self.config['distgroup_sync'])
            distgroup_sync = distgroup_sync_class(forward_sync.entities,
                                                  self.db, self.logger)
            distgroup_conf = adconf.SYNCS[self.config['sync_type']].copy()
            for k, v in adconf.SYNCS[self.config['distgroup_sync']].iteritems():
                distgroup_conf[k] = v
            distgroup_conf['sync_type'] = self.config['sync_type']
            distgroup_sync.configure(distgroup_conf)
            distgroup_sync.fullsync()


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


class UiAForwardSync(BaseSync):
    """Sync for Cerebrum forward mail addresses in AD for UiA.

    """

    default_ad_object_class = 'contact'

    def __init__(self, account_entities, *args, **kwargs):
        """Instantiate forward addresses specific functionality."""
        super(UiAForwardSync, self).__init__(*args, **kwargs)
        self.ac = Factory.get('Account')(self.db)
        self.accounts = account_entities

    def configure(self, config_args):
        """Override the configuration for setting forward specific variables.
    
        """
        super(UiAForwardSync, self).configure(config_args)
        # Which spreads the accounts should have for their forward-addresses
        # to be synchronized
        self.config['account_spreads'] = config_args['account_spreads']

    def fetch_cerebrum_entities(self):
        """Fetch the forward addresses information from Cerebrum, 
        that should be compared against AD. The forward addresses that
        belong to the accounts with specified spreads are fetched.
        
        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it 
        easier to later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        # Get accounts that have all the needed spreads
        self.logger.debug2("Fetching accounts with needed spreads")
        accounts_dict = {}
        account_sets_list = []
        for spread in self.config['account_spreads']:
            tmp_set = set([(row['account_id'], row['name']) for row in
                    list(self.ac.search(spread = spread))])
            account_sets_list.append(tmp_set)
        entity_id2uname = set.intersection(*account_sets_list)

        # Create an AD-object for every forward fetched.
        self.logger.debug("Making forward AD-objects")
        for key, value in entity_id2uname:
            ent = self.accounts.get(value)
            if ent:
                for tmp_addr in ent.maildata.get('forward', []):
                    # Forwarding can sometimes be enabled to local address.
                    # Local addresses then should be ignored
                    if tmp_addr in ent.maildata.get('alias', []):
                        continue
                    name = ','.join((value, tmp_addr, str(ent.entity_id)))
                    self.entities[name] = self.cache_entity(ent.entity_id, name)
                    # All the object attributes are composed based on 
                    # the username and forwardname. Save it for future use
                    self.entities[name].ad_data['uname'] = value
                    self.entities[name].ad_data['faddr'] = tmp_addr


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

