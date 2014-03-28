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
        self.set_attribute('Members', ["CN=" + y.ad_id + "," + y.ou
                                       for y in self.ad_data['members']])


class UiADistGroupSync(BaseSync):
    """Sync for Cerebrum distribution groups in AD for UiA.

    """

    default_ad_object_class = 'group'


    def __init__(self, *args, **kwargs):
        """Instantiate forward addresses specific functionality."""
        super(UiADistGroupSync, self).__init__(*args, **kwargs)
        self.ac = Factory.get('Account')(self.db)
        self.etarget = Email.EmailTarget(self.db)
        self.eforward = Email.EmailForward(self.db)
        self.eaddress = Email.EmailAddress(self.db)
        self.forwards = {}


    def configure(self, config_args):
        """Override the configuration for setting forward specific variables.

        """
        super(UiADistGroupSync, self).configure(config_args)
        self.config['members_config'] = adconf.SYNCS[config_args['member_sync']]


    def fetch_cerebrum_entities(self):
        """Fetch the forward addresses information from Cerebrum, and create
        distribution groups out of it, that will be compared against AD. 
        The forward addresses that belong to the accounts with specified 
        spreads are fetched.
        
        """
        self.logger.debug("Fetching information and making distribution groups")
        subset = self.config['members_config'].get('subset', None)
        # Get accounts that have all the needed spreads
        self.logger.debug2("Fetching accounts with needed spreads")
        accounts_dict = {}
        account_sets_list = []
        for spread in self.config['members_config']['account_spreads']:
            tmp_set = set([(row['account_id'], row['name']) for row in
                    list(self.ac.search(spread = spread))])
            account_sets_list.append(tmp_set)
        entity_id2uname = set.intersection(*account_sets_list)
        for entity_id, username in entity_id2uname:
            accounts_dict[entity_id] = {'uname': username,
                                        'forward_addresses': [],
                                        'local_addresses': []}

        # Generate email target -> entity_id mapping
        self.logger.debug2("Generating email target -> entity_id mapping")
        target_id2target_entity_id = {}
        for row in self.etarget.list_email_targets_ext():
            if row['target_entity_id']:
                target_id2target_entity_id[int(row['target_id'])] = \
                    int(row['target_entity_id'])
        
        # Fetch all local addresses for the accounts
        # Forwarding enables local delivery also, but there is no need
        # to create forward objects for local addresses. Such addresses
        # should be filtered out.
        for row in self.eaddress.search():
            te_id = target_id2target_entity_id.get(int(row['target_id']))
            if te_id in accounts_dict:
                accounts_dict[te_id]['local_addresses'].append(
                    '@'.join((row['local_part'], row['domain']))
                )

        # Fetch all email forwards and save all of them that are enabled,
        # belong to the accounts with needed spreads, and are not local.
        self.logger.debug2("Fetching forwards that belong to the accounts")
        for row in self.eforward.list_email_forwards():
            te_id = target_id2target_entity_id.get(int(row['target_id']))
            if te_id in accounts_dict and row['enable'] == 'T' \
                and row['forward_to'] \
                    not in accounts_dict[te_id]['local_addresses']:
                accounts_dict[te_id]['forward_addresses'].append(
                                               row['forward_to']
                )

        # Create an AD-object for every forward fetched.
        self.logger.debug2("Creating AD-objects for forwards")
        for key, value in accounts_dict.iteritems():
            for tmp_addr in value['forward_addresses']:
                name = ','.join((value['uname'], tmp_addr, str(key)))
                if subset and name not in subset:
                    continue
                ad_entity_class = self._generate_dynamic_class(
                    self.config['members_config']['object_classes'],
                    'forward_for_%s' % value['uname']
                )
                ad_entity_object = ad_entity_class(
                    self.logger, self.config['members_config'], key, name
                )
                self.forwards.setdefault(','.join((value['uname'], str(key))), 
                                         []).append(ad_entity_object)

        for key, value in self.forwards.iteritems():
            name, ent_id = key.split(',')
            self.entities[name] = self.cache_entity(ent_id, name, 
                description = 'Samlegruppe for brukerens forwardadresser')
            self.entities[name].ad_data['members'] = value

