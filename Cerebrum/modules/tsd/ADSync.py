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
import adconf
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
            ent.projectid = pid
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

class ADNetGroupClient(ADUtils.ADclient):
    """Override of the regular AD client to support settings for NIS netgroups.

    The functionality in here should hopefully be generic enough to be
    transferred back to the original ADUtils module.

    Since NisNetGroup doesn't have their own powershell commands, we need to use
    *-ADObject instead of the more specific *-ADGroup, e.g. Get-ADGroup.

    """

    def __init__(self, auth_user, domain_admin, dryrun, domain, *args,
                 **kwargs):
        super(ADNetGroupClient, self).__init__(auth_user, domain_admin, dryrun,
                                               domain, *args, **kwargs)

    attributename_members = 'NisNetGroupTriple'

class NetGroupSync(GroupSync, TSDUtils):
    """TSD's sync of net groups."""

    # We are working with NisNetGroups from the POSIX schema.
    default_ad_object_class = 'nisnetgroup'

    server_class = ADNetGroupClient

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

    def sync_group_members(self, ent):
        """Update the members for a given NisNetGroup.

        Subclassed since NisNetGroups have their members in the attribute
        NisNetGroupTriple and not in the regular 'member'. TODO: This should be
        supported in the regular sync in the future, so change this when the
        member sync has finished.

        """
        self.logger.debug("Syncing members for NisNetGroup: %s" % ent.ad_id)
        cmd = self.server.get_ad_attribute(ent.ad_data['dn'], 'NisNetGroupTriple')
        cere_members = self.get_group_members(ent)
        try:
            ad_members = set(cmd())
        except ADUtils.OUUnknownException:
            if not self.config['dryrun']:
                raise
            self.logger.debug("Dryrun: unknown AD object, simulating "
                              "empty netgroup")
            ad_members = set()
        return self._sync_group_members(ent, cere_members, ad_members)

    def _sync_group_members(self, ent, cere_members, ad_members):
        """Sync the given members to the given NisNetGroup in AD.

        Overriden to support the nisNetgroupTriple attribute (see
        http://msdn.microsoft.com/en-us/library/windows/desktop/ms678985(v=vs.85).aspx
        for its specification). The format of a NisNetGroupTriple attribute:

            (hostname,username,domainname)

        Note that you should only include users as members of these groups.
        Members of the group type must be included in other attributes.

        Example of the attribute:

            (,bobby,example.com)
            (,olabo,)

        TODO: Needs refactoring, should rather have a way of converting each
        member into the attribute format, rather through the adconf.

        """
        groupdn = ent.ad_data['dn']
        # Convert the members into the proper format:
        cere_elements = set('(-,%s,)' % m.ad_id for m in cere_members)
        self.logger.debug("Group has %d members in AD and %d in Cerebrum",
                          len(ad_members), len(cere_elements))
        mem_add = cere_elements - ad_members
        if mem_add:
            self.server.add_members(groupdn, mem_add, 'NisNetGroupTriple')
        mem_remove = ad_members - cere_elements
        if mem_remove:
            self.server.remove_members(groupdn, mem_remove, 'NisNetGroupTriple')
        return True

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

        self.subnet = dns.Subnet.Subnet(self.db)
        self.subnet6 = dns.IPv6Subnet.IPv6Subnet(self.db)

        self.ar = dns.ARecord.ARecord(self.db)
        self.aaaar = dns.AAAARecord.AAAARecord(self.db)

    def fetch_cerebrum_data(self):
        """Override for DNS info."""
        super(HostSync, self).fetch_cerebrum_data()
        # Mapping by dns_owner_id
        self.owner2entity = dict((e.dns_owner_id, e) for e in
                                 self.entities.itervalues())
        self.logger.debug("Found %d owners for entities" %
                          len(self.owner2entity))

        # This is a slow process, so can't be used for too many hosts. Would
        # then have to cache the mapping from ip to subnet.
        self.logger.debug("Fetching IP addresses")
        i = 0
        for row in self.ar.list_ext():
            try:
                ent = self.owner2entity[row['dns_owner_id']]
            except KeyError:
                continue
            ent.ipaddresses.add(row['a_ip'])
            self.subnet.clear()
            try:
                self.subnet.find(row['a_ip'])
            except dns.Errors.SubnetError:
                self.logger.info("No subnet for %s (%s)" % (row['name'],
                                                            row['a_ip']))
                continue
            ent.ipaddresses.add(row['a_ip'])
            ent.vlans.add(self.subnet.vlan_number)
            self.logger.debug2("Host %s (%s): %s (%s)", row['name'],
                               row['dns_owner_id'], row['a_ip'],
                               self.subnet.vlan_number)
            i += 1
        for row in self.aaaar.list_ext():
            try:
                ent = self.owner2entity[row['dns_owner_id']]
            except KeyError:
                continue
            ent.ipaddresses.add(row['aaaa_ip'])
            self.subnet6.clear()
            try:
                self.subnet6.find(row['aaaa_ip'])
            except dns.Errors.SubnetError:
                self.logger.info("No subnet for %s (%s)" % (row['name'],
                                                            row['aaaa_ip']))
                continue
            ent.vlans.add(self.subnet.vlan_number)
            self.logger.debug2("Host %s (%s): %s (%s)", row['name'],
                               row['dns_owner_id'], row['aaaa_ip'],
                               self.subnet6.vlan_number)
            i += 1
        self.logger.debug("Fetched %d VLAN numbers" % i)

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
                self.logger.debug2("Host not connected to project: %s" % name)
                continue
            try:
                self.entities[name] = self.cache_entity(row["host_id"],
                                        name, row['dns_owner_id'],
                                        host2pid[row['dns_owner_id']],
                                        row['name'])
            except Errors.CerebrumError, e:
                self.logger.warn("Could not cache %s: %s" % (name, e))
                continue

    def cache_entity(self, entity_id, entity_name, dns_owner_id, pid, fqdn):
        """Cache a DNS entity."""
        # TODO: subclass CerebrumEntity for hosts?
        ent = self._object_class(self.logger, self.config, entity_id,
                                 entity_name)
        ent.dns_owner_id = dns_owner_id
        ent.ou = 'OU=hosts,OU=resources,OU=%s,%s' % (pid,
                                                     self.config['target_ou'])
        ent.fqdn = fqdn
        return ent

class HostEntity(CerebrumEntity):
    """A TSD host"""
    def __init__(self, *args, **kwargs):
        super(HostEntity, self).__init__(*args, **kwargs)
        self.ipaddresses = set()
        self.fqdn = None
        self.vlans = set()
        self.vlan = None

    def calculate_ad_values(self):
        """Overriden to add TSD specific values."""
        super(HostEntity, self).calculate_ad_values()

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
        """Initialize the sync with hostpolicy objects.."""
        super(HostpolicySync, self).__init__(db, logger)
        self.component = PolicyComponent(self.db)
        self.role = Role(self.db)
        self.atom = Atom(self.db)

    def configure(self, config_args):
        """Add Hostpolicy specific configuration."""
        super(HostpolicySync, self).configure(config_args)
        self.rolepath = ','.join(('OU=roles', self.config['target_ou']))
        self.atompath = ','.join(('OU=atoms', self.config['target_ou']))

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
        # TODO: Change this to rather be using config['object_classes']:
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

    def sync_groups_members(self):
        """Override, to simulate hostpolicies as groups in AD."""
        self._roledns = {}
        self._atomdns = {}
        self._hostdns = {}

        # TODO: The hardcoded functionality here should be generalized and be
        # modifiable through adconf.

        # Fetch roles
        cmd = self.server.start_list_objects(self.rolepath,
                                             ('Name', 'DistinguishedName',),
                                             'group')
        for obj in self.server.get_list_objects(cmd):
            name = obj['Name']
            dn = obj['DistinguishedName']
            if name in self._roledns:
                self.logger.warn("Skipping, more than one member match "
                                 "for: %s (%s)", name, dn)
                continue
            self._roledns[name] = dn
        # Fetch atoms
        cmd = self.server.start_list_objects(self.atompath,
                                             ('Name', 'DistinguishedName',),
                                             'group')
        for obj in self.server.get_list_objects(cmd):
            name = obj['Name']
            dn = obj['DistinguishedName']
            if name in self._atomdns:
                self.logger.warn("Skipping, more than one member match "
                                 "for: %s (%s)", name, dn)
                continue
            self._atomdns[name] = dn
        self.logger.debug("Found %d roles and %d atoms in AD", len(self._roledns),
                          len(self._atomdns))

        # Fetch hosts:
        cmd = self.server.start_list_objects(adconf.SYNCS['hosts']['target_ou'],
                                             ('Name', 'DistinguishedName',),
                                             'computer') 
        # TODO: The hosts config should be fetched from the hosts sync and not
        # hardcoded.
        for obj in self.server.get_list_objects(cmd):
            name = obj['Name'].lower()
            dn = obj['DistinguishedName']
            if name in self._hostdns:
                self.logger.warn("Skipping, more than one member match in AD "
                                 "for: %s (%s)", name, dn)
                continue
            self._hostdns[name] = dn
        self.logger.debug("Found %d hosts in AD", len(self._hostdns))

        return super(HostpolicySync, self).sync_groups_members()

    def get_group_members(self, ent):
        """Override the default member retrieval to fetch policy relations.

        We need to fetch both policy components and hosts they are connected to.

        """
        # TODO: This is hardcoded for now, should be changed when we find a
        # generic solution for specifying the OU path of member objects in AD:
        hostpath = adconf.SYNCS['hosts']['target_ou']

        # Get policy members of the component:
        members = set()
        for row in self.component.search_relations(
                               target_id=ent.entity_id,
                               relationship_code=self.co.hostpolicy_contains,
                               indirect_relations=False):
            name = self.config['name_format'] % row['source_name']
            dn = None
            if row['source_entity_type'] == self.co.entity_hostpolicy_role:
                dn = self._roledns.get(name)
                if not dn:
                    self.logger.warn("No such role in AD: %s", name)
                    continue
            elif row['source_entity_type'] == self.co.entity_hostpolicy_atom:
                dn = self._atomdns.get(name)
                if not dn:
                    self.logger.warn("No such atom in AD: %s", name)
                    continue
            else:
                self.logger.warn("Unknown entity_type %s for relation: %s",
                                 row['source_entity_type'], row['source_name'])
                continue
            members.add(dn)
        # Get host members of the component:
        hostname_format = adconf.SYNCS['hosts'].get('name_format', '%s')
        for row in self.component.search_hostpolicies(policy_id=ent.entity_id):
            name = hostname_format % row['dns_owner_name']
            name = name.lower()
            name = self._hostname2adid(name)
            dn = self._hostdns.get(name)
            if not dn:
                self.logger.warn("No such host in AD: %s" % name)
            else:
                members.add(dn)
        return members
