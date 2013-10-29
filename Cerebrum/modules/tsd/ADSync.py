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

"""AD-sync extensions that is specific for the TSD project.

TSD (Tjeneste for Sensitive Data) have some extra needs in their sync, as they
use AD for managing the whole system, including linux machines. Some of this
is not a part of the generic AD-sync.

"""

import time
import pickle

import cerebrum_path
import cereconf
from Cerebrum.Utils import unicode2str, Factory, dyn_import, sendmail
from Cerebrum import Entity, Errors
from Cerebrum.modules import EntityTrait
from Cerebrum.modules import CLHandler
from Cerebrum.modules import dns

from Cerebrum.modules.ad2.CerebrumData import CerebrumEntity
from Cerebrum.modules.ad2.CerebrumData import CerebrumGroup
from Cerebrum.modules.ad2 import ADSync
from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.modules.ad2.winrm import PowershellException

from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent
from Cerebrum.modules.hostpolicy.PolicyComponent import Role, Atom

class TSDUtils(ADSync.BaseSync):
    """Class for utility methods for the AD-syncs for TSD.

    This class should be a part of all the sync classes used by TSD, as it adds
    some helper methods, e.g. for getting the correct OU and parsing the domain.

    """
    def __init__(self, *args, **kwargs):
        super(TSDUtils, self).__init__(*args, **kwargs)
        self.ou = Factory.get('OU')(self.db)
        self.dnsowner = dns.DnsOwner.DnsOwner(self.db)
        self.subnet = dns.Subnet.Subnet(self.db)
        self.subnet6 = dns.IPv6Subnet.IPv6Subnet(self.db)
        self.ar = dns.ARecord.ARecord(self.db)
        self.aaaar = dns.AAAARecord.AAAARecord(self.db)

    def _parse_dns_owner_name(self, raw_name):
        """Parse a DNS name into the name format to be included in AD.

        AD does not accept punctuation in an object's Name, so only the first
        part of the name is returned. Example:

            example.domain.usit.no. -> (example, domain)

        Note that this could create conflicts if subdomains are used, and you
        have two domain names that are equal, but in different subdomains. If
        they're put in the same OU they would override each other.

        TODO: Must be updated when we know how TSD's data should look like.

        @type raw_name: string
        @param raw_name: The FQDN of a host.

        @rtype: list
        @return: A list with the domain name as the first element, and any
            subdomain in the following elements. The main top domains (e.g.
            uio.no. and usit.no.) are stripped out.

        """
        if raw_name.endswith('.'):
            return raw_name.split('.')[:-3]
        else:
            return raw_name.split('.')[:-2]

    def _generate_ou_path(self, ent):
        """Return the correct OU path for an object in AD.

        Each project in TSD has its own OU where the project's objects and
        everything else should be put. Sub OUs are used for the different object
        types and other behaviour.

        One important detail to remember as well is that a object, e.g. an
        account can *only* be a part of a single project.

        @rtype: string
        @return: The full OU path for the object.

        """
        # TODO
        return ','.join((self.config['target_ou'],))

    def _map_host_to_ou(self, dns_owner_id):
        """Return the proper project ID for where a given hosts belongs.

        Hosts are in TSD not directly registered on a project, but their subnets
        are. We therefore find the subnet of the host, and find out in what
        project the subnet belongs.

        @type dns_owner_id: int
        @param dns_owner_id:
            The entity_id of the DnsOwner that should belong to a project.

        @rtype: string
        @return:
            The project ID for the OU that the subnet belongs to, and therefore
            also the host.

        """
        if not hasattr(self, '_subnet2ou'):
            # Cache the subnet mapping the first time it's used:
            ent = EntityTrait.EntityTrait(self.db)
            self._subnet2ou = dict((r['entity_id'], r['target_id']) for r in
                                   ent.list_traits(code=(
                                               self.co.trait_project_subnet,
                                               self.co.trait_project_subnet6)))
            self._ou2pid = dict((r['entity_id'], r['external_id']) for r in
                                self.ou.search_external_ids(
                                        id_type=self.co.externalid_project_id))
        pids = set()
        for row in self.ar.list_ext(dns_owner_id=dns_owner_id):
            self.subnet.clear()
            try:
                self.subnet.find(row['a_ip'])
            except (Errors.NotFoundError, dns.Errors.SubnetError):
                self.logger.debug("Ignoring IP %s, not in subnet", row['a_ip'])
                continue
            if self.subnet.entity_id not in self._subnet2ou:
                self.logger.debug("Ignoring subnet %s, not mapped to PID",
                                  self.subnet.entity_id)
                continue
            pids.add(self._ou2pid[self._subnet2ou[self.subnet.entity_id]])
        for row in self.aaaar.list_ext(dns_owner_id=dns_owner_id):
            self.subnet6.clear()
            try:
                self.subnet6.find(row['aaaa_ip'])
            except (Errors.NotFoundError, dns.Errors.SubnetError):
                self.logger.debug("Ignoring IP %s, not in subnet", row['aaaa_ip'])
                continue
            if self.subnet6.entity_id not in self._subnet2ou:
                self.logger.debug("Ignoring subnet %s, not mapped to PID",
                                  self.subnet6.entity_id)
                continue
            pids.add(self._ou2pid[self._subnet2ou[self.subnet6.entity_id]])
        if len(pids) > 1:
            raise Errors.TooManyRowsError("dns_owner %s mapped to %d projects" %
                                          (dns_owner_id, len(pids)))
        if not pids:
            raise Errors.NotFoundError("No project found for dns_owner %s" %
                                       dns_owner_id)
        return pids.pop()

class HostSync(ADSync.HostSync, TSDUtils):
    """A hostsync, using the DNS module instead of the basic host concept.

    The sync is not a sync of DNS, as it does not handle all the details that is
    needed for a complete sync of DNS data. The sync does only create the host
    entities as computer objects in AD, and updates their attributes for now. If
    AD-DNS should be updated, we need to sync a lot more details.

    """
    def __init__(self, *args, **kwargs):
        """Instantiate dns specific functionality."""
        super(HostSync, self).__init__(*args, **kwargs)

    def fetch_cerebrum_entities(self):
        """Fetch the hosts from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier to
        later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        self.logger.debug("Fetching all DNS hosts")
        # Create a map from host to 

        # We are not using spread for hosts in TSD, for now...
        subset = self.config.get('subset')
        for row in self.dnsowner.search():
            # TBD: Is it correct to only get the first part of the host, or
            # should we for instance add sub domains to sub-OUs?
            name = row['name'].split('.')[0]
            if subset and name not in subset:
                continue
            try:
                self.entities[name] = self.cache_entity(row["dns_owner_id"],
                                                        name)
            except Errors.CerebrumError, e:
                self.logger.warn("Could not cache %s: %s" % (name, e))
                continue

    def cache_entity(self, entity_id, entity_name):
        """Cache a DNS entity."""
        pid = self._map_host_to_ou(entity_id)
        # TODO: subclass CerebrumEntity for hosts?
        ent = CerebrumEntity(self.logger, self.config, entity_id, entity_name)
        ent.ou = 'OU=hosts,OU=%s,%s' % (pid, self.config['target_ou'])
        return ent

class HostpolicySync(ADSync.GroupSync, TSDUtils):
    """Class for syncing all hostpolicy components to AD.

    Note that the spread set for this sync is not used, at least for now, as
    we sync *all* hostpolicy components. This could be changed in the future,
    if we only need a subset of the components.

    The Roles and Atoms are considered as Group objects in AD, since AD does
    not have a native way of describing policy components. The group
    memberships must be considered the policy relationships. Hosts added as
    members of a policy group must be considered to have this policy set.

    """
    def __init__(self, db, logger):
        """Initialize the sync with hostpolicy objects..

        """
        super(HostpolicySync, self).__init__(db, logger)
        self.component = PolicyComponent(self.db)
        self.role = Role(self.db)
        self.atom = Atom(self.db)

    def configure(self, config_args):
        """Add Hostpolicy specific configuration.

        """
        super(HostpolicySync, self).configure(config_args)
        # TODO

    def setup_server(self):
        """Add hostpolicy functionality for the server object."""
        super(HostpolicySync, self).setup_server()
        # We must convert policies to Group objects in AD:
        self.server.entity_type_map['hostpolicy_role'] = 'Group'
        self.server.entity_type_map['hostpolicy_atom'] = 'Group'

    def fetch_cerebrum_entities(self):
        """Fetch the policycomponents from Cerebrum to be compared with AD.

        """
        self.logger.debug("Fetching all hostpolicies")
        subset = self.config.get('subset')
        for row in self.component.search():
            name = row["name"].strip()
            if subset and name not in subset:
                continue
            self.entities[name] = self.cache_entity(int(row["component_id"]),
                                                    name, row)

    def cache_entity(self, entity_id, entity_name, data):
        """Wrapper method for creating a cache object for an entity. 
        
        You should call this method for new cache objects instead of creating it
        directly, for easier subclassing.

        @type data: dict
        @param data: A row object with data about the entity to cache.

        """
        ent = CerebrumGroup(self.logger, self.config, entity_id, entity_name,
                            data['description'])
        # Feed the entity with the given data:
        for key in ('entity_type', 'create_date', 'foundation',
                    'foundation_date'):
            setattr(ent, key, data[key])
        if data['entity_type'] == self.co.entity_hostpolicy_atom:
            ent.ou = ','.join(('OU=Atoms', self.config['target_ou']))
        elif data['entity_type'] == self.co.entity_hostpolicy_role:
            ent.ou = ','.join(('OU=Roles', self.config['target_ou']))
        else:
            self.logger.warn("Unknown entity type for %s: %s", entity_id,
                             data['entity_type'])
        return ent

    def start_fetch_ad_data(self, object_type=None, attributes=()):
        """Send request(s) to AD to start generating the data we need.

        Could be subclassed to get more/other data.

        @type object_type: Constant of EntityTypeCode
        @param object_type: The type of objects that should be returned from AD.
            If not set, the value in L{config['target_type']} is used.

        @type attributes: list
        @param attributes: Extra attributes that should be retrieved from AD.
            The attributes defined in the config is already set.

        @rtype: string
        @return: A CommandId that is the servere reference to later get the data
            that has been generated.

        """
        if not object_type:
            object_type = self.config['target_type']
        attrs = self.config['attributes'].copy()
        if attributes:
            attrs.extend(attributes)
        # Some attributes are readonly, so they shouldn't be put in the list,
        # but we still need to receive them if they are used, like the SID.
        if self.config['store_sid'] and 'SID' not in attrs:
            attrs['SID'] = None
        return self.server.start_list_objects(ou = self.config['search_ou'],
                                              attributes = attrs,
                                              object_type = object_type)

    def sync_group_members(self, ent):
        """Override the member sync to work on policy relationships.

        The policies' relationships are turned around when in AD, to support
        automatic inheritance within the policy groups. The host memberships
        works in the same way as in the hostpolicy module.

        """
        self.logger.debug("Syncing policy members for: %s" % ent.ad_id)
        # Start fetching the member list from AD:
        cmdid = self.server.start_list_members(ent.ad_data['dn'])
        # Get policy members of the component:
        members = set()
        for row in self.component.search_relations(target_id=ent.entity_id,
                                  relationship_code=self.co.hostpolicy_contains,
                                  indirect_relations=False):
            members.add(self.config['name_format'] % row['target_name'])
        # Get host members of the component:
        for row in self.component.search_hostpolicies(policy_id=ent.entity_id):
            parts = self._parse_dns_owner_name(row['dns_owner_name'])
            members.add(parts[0]) # TODO: what to do with subdomains?
        return self._sync_group_members(ent, members, cmdid)

