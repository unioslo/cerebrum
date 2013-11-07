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
        self.et = EntityTrait.EntityTrait(self.db)

        self.dnsowner = dns.DnsOwner.DnsOwner(self.db)
        self.subnet = dns.Subnet.Subnet(self.db)
        self.subnet6 = dns.IPv6Subnet.IPv6Subnet(self.db)
        self.ar = dns.ARecord.ARecord(self.db)
        self.aaaar = dns.AAAARecord.AAAARecord(self.db)

    def _hostname2adid(self, hostname):
        """Parse a DNS host name into the name format to be included in AD.

        AD does not accept punctuation in an object's Name. For now, we only
        return the leftmost part of the name. Note that this would create
        conflicts if subdomains are used, and two different host use the same
        base name in two different domains. They would then override each other.

        TODO: What to do with subdomains?

        @type raw_name: string
        @param raw_name: The FQDN of a host.

        @rtype: list
        @return: A list with the domain name as the first element, and any
            subdomain in the following elements. The main top domains (e.g.
            uio.no. and usit.no.) are stripped out.

        """
        if '.' not in hostname:
            return hostname
        return hostname.split('.')[0]

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

    def _get_ou_pid(self, ou_id):
        """Get the corresponding project ID for a given ou_id.

        This is a method to be able to cache the mapping and get faster response
        the next time asked. Suitable if you need to fetch the project ID for a
        lot of OUs, but if you should only fetch it for a single OU, it would be
        a bit more efficient to run L{ou.get_project_id()} directly.

        @rtype: string
        @return: The project ID for the given OU.

        @raise KeyError: 
            If OU does not exist or if the OU does not have a project ID.

        """
        if not hasattr(self, '_ou2pid'):
            self._ou2pid = dict((r['entity_id'], r['external_id']) for r in
                                self.ou.search_external_ids(
                                        id_type=self.co.externalid_project_id))
            self.logger.debug2("Found %d project OUs", len(self._ou2pid))
        return self._ou2pid[ou_id]

class UserSync(ADSync.UserSync, TSDUtils):
    """TSD's sync of users."""

    def fetch_cerebrum_entities(self):
        """Fetch the users from Cerebrum.

        Overridden to only get accounts affiliated with projects.

        @rtype: list
        @return: A list of targeted entities from Cerebrum, wrapped into
            L{CerebrumData} objects.

        """
        # Get a mapping of the accounts to projects
        ac2ouid = dict((r['account_id'], r['ou_id']) for r in
                      self.ac.list_accounts_by_type(
                          affiliation=self.co.affiliation_project,
                          filter_expired=True, primary_only=False,
                          account_spread=self.config['target_spread']))
        self.logger.debug("Mapped %d account to OUs" % len(ac2ouid))

        # Find all users with defined spread(s):
        self.logger.debug("Fetching users with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        for row in self.ac.search(spread=self.config['target_spread']):
            uname = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and uname not in subset:
                continue
            if row['account_id'] not in ac2ouid:
                continue
            try:
                pid = self._get_ou_pid(ac2ouid[row['account_id']])
            except KeyError, e:
                self.logger.warn("Unknown project ID for %s", row['account_id'])
                continue
            ent = self.cache_entity(int(row["account_id"]), uname,
                                    owner_id=int(row["owner_id"]),
                                    owner_type=int(row['owner_type']))
            ent.ou = 'OU=users,OU=%s,%s' % (pid, self.config['target_ou'])
            self.entities[uname] = ent

class GroupSync(ADSync.GroupSync, TSDUtils):
    """TSD's sync of file groups."""

    def fetch_cerebrum_data(self):
        """Subclassed to also fetch TSD data from Cerebrum, like projects"""
        self.entity2pid = dict((r['entity_id'],
                               self._get_ou_pid(r['target_id'])) for r in
                               self.gr.list_traits(code=self.co.trait_project_group))
        self.logger.debug("Mapped %d entities to projects" % len(self.entity2pid))
        return super(GroupSync, self).fetch_cerebrum_data()

    def fetch_cerebrum_entities(self):
        """Overridden to only fetch groups affiliated with projects."""
        self.logger.debug("Fetching groups with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        for row in self.gr.search(spread=self.config['target_spread']):
            gname = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and gname not in subset:
                continue
            try:
                pid = self.entity2pid[row['group_id']]
            except KeyError, e:
                self.logger.warn("Unknown project ID for: %s", gname)
                continue
            ent = self.cache_entity(row["group_id"], gname, row['description'])
            ent.ou = 'OU=filegroups,OU=%s,%s' % (pid, self.config['target_ou'])
            self.entities[gname] = ent

class NetGroupSync(GroupSync):
    """TSD's sync of net groups."""

    def fetch_cerebrum_entities(self):
        """Overridden to only fetch groups affiliated with projects."""
        self.logger.debug("Fetching groups with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        for row in self.gr.search(spread=self.config['target_spread']):
            gname = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and gname not in subset:
                continue
            try:
                pid = self.entity2pid[row['group_id']]
            except KeyError, e:
                self.logger.warn("Unknown project ID for %s", gname)
                continue
            ent = self.cache_entity(row["group_id"], gname, row['description'])
            ent.ou = 'OU=netgroups,OU=%s,%s' % (pid, self.config['target_ou'])
            self.entities[gname] = ent

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
        self.host = dns.HostInfo.HostInfo(self.db)

    def fetch_cerebrum_entities(self):
        """Fetch the hosts from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier to
        later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        self.logger.debug("Fetching all DNS host traits")
        host2pid = dict((r['entity_id'], self._get_ou_pid(r['target_id'])) for r
                        in self.et.list_traits(code=self.co.trait_project_host))
        self.logger.debug("Fetched %d hosts mapped to projects" % len(host2pid))
        self.logger.debug("Fetching all DNS hosts")
        subset = self.config.get('subset')
        for row in self.host.search(): # Might want to use a spread later
            # TBD: Is it correct to only get the first part of the host, or
            # should we for instance add sub domains to sub-OUs?
            name = self._hostname2adid(row['name'])
            if subset and name not in subset:
                continue
            if row['dns_owner_id'] not in host2pid:
                # Host is not connected to a project, and is therefore ignored.
                continue
            try:
                self.entities[name] = self.cache_entity(row["dns_owner_id"],
                                        name, host2pid[row['dns_owner_id']])
            except Errors.CerebrumError, e:
                self.logger.warn("Could not cache %s: %s" % (name, e))
                continue

    def cache_entity(self, entity_id, entity_name, pid):
        """Cache a DNS entity."""
        # TODO: subclass CerebrumEntity for hosts?
        ent = CerebrumEntity(self.logger, self.config, entity_id, entity_name)
        ent.ou = 'OU=hosts,OU=resources,OU=%s,%s' % (pid,
                                                     self.config['target_ou'])
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
            ent.ou = ','.join(('OU=atoms', self.config['target_ou']))
        elif data['entity_type'] == self.co.entity_hostpolicy_role:
            ent.ou = ','.join(('OU=roles', self.config['target_ou']))
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

    def get_group_members(self, ent):
        """Override the default member retrieval to fetch policy relations.

        We need to fetch both policy components and hosts they are connected to.

        """
        # Get policy members of the component:
        members = set()
        for row in self.component.search_relations(target_id=ent.entity_id,
                                  relationship_code=self.co.hostpolicy_contains,
                                  indirect_relations=False):
            members.add(self.config['name_format'] % row['source_name'])
        # Get host members of the component:
        for row in self.component.search_hostpolicies(policy_id=ent.entity_id):
            members.add(self._hostname2adid(row['dns_owner_name']))
        return members
