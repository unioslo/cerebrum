#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
"""Job for syncing Cerebrum data with TSD's Gateway (GW).

The Gateway needs information about all projects, accounts, hosts, subnets and
VLANs, to be able to let users in to the correct project.
This information comes from Cerebrum. Some of the information is sent to the
Gateway e.g through bofh commands and the import from Nettskjema, but not all
information gets update that way.
An example is quarantines that gets activated or deactivated.
"""
from __future__ import unicode_literals

import six

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.dns.Errors import SubnetError

# Parts of the DNS module raises bofhd exceptions. Need to handle this:
from Cerebrum.modules.dns import (IPv6Subnet, Subnet, AAAARecord, ARecord,
                                  IPv6Utils)
from Cerebrum.modules.tsd import Gateway

# Global logger
logger = Factory.get_logger('cronjob')


def print_config():
    """Print cereconf."""
    # Mostly to get rid of linter errors
    print('cereconf: {}'.format(cereconf))


# Structure used to compare projects in Cerbrum and Gateway.
# TODO: Not used yet
#
#   class Project(object):
#
#       """Container of a project and its data.
#
#       This is to ease the comparement of projects with the Gateway.
#
#       """
#       def __init__(self, entity_id):
#           self.entity_id = entity_id


class Processor:
    """The processor class, doing the sync with the gateway."""

    def __init__(self, gw, dryrun):
        self.gw = gw
        self.dryrun = dryrun
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.ent = Factory.get('Entity')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pu = Factory.get('PosixUser')(self.db)
        self.pg = Factory.get('PosixGroup')(self.db)
        self.subnet6 = IPv6Subnet.IPv6Subnet(self.db)
        self.subnet = Subnet.Subnet(self.db)

        if self.dryrun:
            logger.info("Dryrun sync, no gateway changes will be performed")

        # Map account_id to account_name:
        self.acid2acname = dict(
            (row['account_id'], row['name']) for row in
            self.ac.search(spread=self.co.spread_gateway_account))
        logger.debug2("Found %d accounts", len(self.acid2acname))

        # Quarantined OUs (ou_id)
        self.quarantined_ous = set(r['entity_id'] for r in
                                   self.ou.list_entity_quarantines(
                                       entity_types=self.co.entity_ou,
                                       only_active=True))
        logger.debug2("Found %d quarantined projects",
                      len(self.quarantined_ous))

        # Map ou_id to project id:
        self.ouid2pid = dict((row['entity_id'], row['external_id']) for row in
                             self.ou.search_external_ids(
                                 entity_type=self.co.entity_ou,
                                 id_type=self.co.externalid_project_id)
                             if row['entity_id'] not in self.quarantined_ous)
        logger.debug2("Found %d project IDs", len(self.ouid2pid))

    def process(self):
        """
        Sync Cerebrum and Gateway.

        Goes through all data from the Gateway, and compare it with Cerebrum.
        If the Gateway contains mismatches, it should be updated with master
        data from Cerebrum.
        """
        logger.info("Start processing projects")
        self.process_projects()
        logger.info("Processing projects done")

        logger.info("Start processing users")
        self.process_users()
        logger.info("Processing users done")

        logger.info("Start processing DNS data")
        self.process_dns()
        logger.info("Processing DNS data done")

        logger.info("Start processing groups")
        self.process_groups()
        logger.info("Processing groups done")

    def process_projects(self):
        """Sync all projects with the GW.

        NOTE: There's an expensive clear-find loop here that could be optimized
        by caching.
        """
        processed = set()
        # Update existing projects:
        for proj in self.gw.list_projects():
            pid = proj['name']
            try:
                self.process_project(pid, proj)
            except Gateway.GatewayException, e:
                logger.warn("GatewayException for %s: %s" % (pid, e))
            processed.add(pid)

        # Add new OUs:
        # TODO: A bug in ou.search does not handle filtering on quarantines
        # that are not active (yet), as they won't get returned even though
        # they should. This should be fixed in the API, but as it affects quite
        # a few exports, it requires a bit more effort.
        for row in self.ou.search():
            self.ou.clear()
            self.ou.find(row['ou_id'])
            if self.ou.get_entity_quarantine(only_active=True):
                logger.debug3("Skipping quarantined project with ou_id=%s",
                              self.ou.entity_id)
                continue
            try:
                pid = self.ou.get_project_id()
            except Errors.NotFoundError, e:
                logger.warn("No project id for ou_id %s: %s", row['ou_id'], e)
                continue
            if pid in processed:
                logger.debug4('Skipping already processed project: %s', pid)
                continue
            logger.debug2('Creating project: %s', pid)
            self.gw.create_project(pid, self.ou.expire_date)
            processed.add(pid)

    def process_project(self, pid, proj):
        """Process a given project retrieved from the GW.

        The information should be retrieved from the gateway, and is then
        matched against what exist in Cerebrum.

        :param string pid:
            The project ID.

        :param dict proj:
            Contains the information about a project and all its elements.
        """
        logger.debug("Processing project %s: %s", pid, proj)
        self.ou.clear()
        try:
            self.ou.find_by_tsd_projectid(pid)
        except Errors.NotFoundError:
            logger.debug("Project %s not found in Cerebrum", pid)
            # TODO: check if the project is marked as 'expired', so we don't
            # send this to the gw every time.
            # if proj['expires'] and proj['expires'] < DateTime.now():
            self.gw.delete_project(pid)
            return

        if proj['expires'] != self.ou.expire_date:
            self.gw.expire_project(pid, self.ou.expire_date)

        # Since no other quarantine types are handled in this method
        # we only need to select quarantine type frozen
        # This may change in the future

        quars = [row for row in self.ou.get_entity_quarantine(
            self.co.quarantine_frozen)]

        # TBD: Delete project when put in end quarantine, or wait for the
        # project to have really been removed? Remember that we must not remove
        # the OU completely, to avoid reuse of the project ID and project name,
        # so we will then never be able to delete it from the GW, unless we
        # find a way to delete it.

        # if self.co.quarantine_project_end in quars:
        #     logger.debug("Project %s has ended" % pid)
        #     self.gw.delete_project(pid)
        if quars:
            # sort here in order to be able to show the same list in the log
            quars.sort(key=lambda v: v['start_date'])  # sort by start_date
            when = quars[0]['start_date']  # the row with the lowest start_date
            logger.debug("Project %s has freeze-quarantines: %s",
                         pid,
                         six.text_type(quars))
            if proj['frozen']:
                if proj['frozen'] != when:  # the freeze dates are different
                    self.gw.freeze_project(pid, when)  # set new freeze date
            else:
                self.gw.freeze_project(pid, when)
        else:
            if proj['frozen']:
                self.gw.thaw_project(pid)

    def process_users(self):
        """Sync all users with the GW."""
        processed = set()

        # Get the mapping to each project. Each user can only be part of one
        # project.
        ac2proj = dict()
        for row in self.pu.list_accounts_by_type(
                affiliation=self.co.affiliation_project,
                filter_expired=True,
                account_spread=self.co.spread_gateway_account):
            if row['account_id'] in ac2proj:
                logger.warn("Account %s affiliated with more than one project",
                            row['account_id'])
                continue
            ac2proj[row['account_id']] = row['ou_id']
        logger.debug2("Found %d accounts connected with projects",
                      len(ac2proj))

        # Update existing projects:
        for usr in self.gw.list_users():
            try:
                self.process_user(usr, ac2proj)
            except Gateway.GatewayException, e:
                logger.warn("GW exception for user %s: %s", usr['username'],
                            e)
            processed.add(usr['username'])

        # Add new users:
        for row in self.pu.search(spread=self.co.spread_gateway_account):
            if row['name'] in processed:
                continue
            logger.debug2("User not known by GW: %s" % row['name'])
            self.pu.clear()
            try:
                self.pu.find(row['account_id'])
            except Errors.NotFoundError:
                logger.debug("Skipping non-posix user: %s", row['name'])
                continue
            # Skip quarantined accounts:
            if tuple(self.pu.get_entity_quarantine(only_active=True)):
                logger.debug2("Skipping unknown, quarantined account: %s",
                              row['name'])
                continue
            # Skip accounts not affiliated with a project.
            pid = self.ouid2pid.get(ac2proj.get(self.pu.entity_id))
            if not pid:
                logger.debug("Skipping non-affiliated account: %s",
                             self.pu.entity_id)
                continue
            self.gw.create_user(pid,
                                row['name'],
                                self.pu.posix_uid,
                                expire_date=self.pu.expire_date)

    def process_user(self, gw_user, ac2proj):
        """Process a single user retrieved from the GW.

        :param dict gw_user: The data about the user from the GW.

        :param dict ac2proj:
            A mapping from account_id to the ou_id of the project it belongs
            to.
        """
        username = gw_user['username']
        logger.debug2("Process user %s: %s" % (username, gw_user))

        try:
            pid = gw_user['project']
        except KeyError:
            logger.error("Missing project from GW for user: %s", username)
            return

        self.pu.clear()
        try:
            self.pu.find_by_name(username)
        except Errors.NotFoundError:
            logger.info("User %s not found in Cerebrum" % username)
            self.gw.delete_user(pid, username)
            return

        if gw_user['expires'] != self.pu.expire_date:
            self.gw.expire_user(pid, username, self.pu.expire_date)

        # Skip accounts not affiliated with a project.
        if self.pu.entity_id not in ac2proj:
            logger.info("User %s not affiliated with any project" % username)
            self.gw.delete_user(pid, username)
            return
        if ac2proj[self.pu.entity_id] in self.quarantined_ous:
            logger.info("User %s affiliated with a quarantined project",
                        username)
            if not gw_user['frozen']:
                self.gw.freeze_user(pid, username)
            return
        if pid != self.ouid2pid.get(ac2proj[self.pu.entity_id]):
            logger.error("Danger! Project mismatch in Cerebrum and GW for "
                         "account %s (entity_id=%s, gw_pid=%s, crb_pid=%s)",
                         username, self.pu.entity_id, pid,
                         self.ouid2pid.get(ac2proj[self.pu.entity_id]))
            if not gw_user['frozen']:
                self.gw.freeze_user(pid, username)
            return
        quars = [row for row in self.pu.get_entity_quarantine(
            filter_disable_until=True)]
        if quars:
            # sort here in order to be able to show the same list in the log
            quars.sort(key=lambda v: v['start_date'])  # sort by start_date
            when = quars[0]['start_date']  # the row with the lowest start_date
            logger.debug2('User {username} has quarantines: {quars}'.format(
                username=username,
                quars=six.text_type(quars)))
            if gw_user['frozen']:
                if gw_user['frozen'] != when:  # the freeze dates are different
                    self.gw.freeze_user(pid, username, when)  # set new freeze
            else:
                self.gw.freeze_user(pid, username, when)
        else:
            if gw_user['frozen']:
                self.gw.thaw_user(pid, username)

    def process_groups(self):
        """Sync all groups with the GW."""
        # Mapping from group_id to project's ou_id:
        gr2proj = dict((r['entity_id'], r['target_id']) for r in
                       self.ent.list_traits(code=self.co.trait_project_group)
                       if r['target_id'] in self.ouid2pid)
        logger.debug2("Found %d groups affiliated with projects",
                      len(gr2proj))
        processed = set()

        # Update existing projects:
        for grp in self.gw.list_groups():
            try:
                self.process_group(grp, gr2proj)
            except Gateway.GatewayException, e:
                logger.warn("GW exception for group %s: %s",
                            grp['groupname'], e)
            processed.add(grp['groupname'])

        # Add new groups:
        for row in self.pg.search(spread=self.co.spread_file_group):
            if row['name'] in processed:
                continue
            logger.debug2("Group not known by GW: %s" % row['name'])
            # Skip groups not affiliated with a project.
            pid = self.ouid2pid.get(gr2proj.get(row['group_id']))
            if not pid:
                logger.debug("Skipping non-affiliated group: %s",
                             self.pg.entity_id)
                continue
            self.pg.clear()
            try:
                self.pg.find(row['group_id'])
            except Errors.NotFoundError:
                logger.debug("Skipping non-posix group: %s", row['name'])
                continue

            gwdata = self.gw.create_group(pid, row['name'], self.pg.posix_gid)
            self.process_group(gwdata, gr2proj)

    def process_group(self, gw_group, gr2proj):
        """Process a single group retrieved from the GW.

        :param dict gw_group: The data about the group from the GW.

        :param dict gr2proj:
            A mapping from group_id to the ou_id of the project it belongs to.
        """
        groupname = gw_group['groupname']
        logger.debug2("Process group %s: %s" % (groupname, gw_group))
        try:
            pid = gw_group['project']
        except KeyError:
            logger.error("Missing project from GW for group: %s", groupname)
            return
        self.pg.clear()
        try:
            self.pg.find_by_name(groupname)
        except Errors.NotFoundError:
            logger.info("Group %s not found in Cerebrum" % groupname)
            self.gw.delete_group(pid, groupname)
            return
        # Skip accounts not affiliated with a project.
        if not gr2proj.get(self.pg.entity_id):
            logger.info("Group %s not affiliated with any project" % groupname)
            self.gw.delete_group(pid, groupname)
            return
        if pid != self.ouid2pid.get(gr2proj[self.pg.entity_id]):
            logger.warn("Project mismatch for group %s" % self.pg.entity_id)
            # Deleting for now, would be created at next run of this script:
            self.gw.delete_group(pid, groupname)
            return

        # Fixing the memberships. Only updating user members for now, and
        # therefore including indirect members. The GW might need other member
        # types later.
        cere_members = set(
            r['member_name'] for r in self.pg.search_members(
                group_id=self.pg.entity_id,
                member_type=self.co.entity_account,
                indirect_members=True,
                member_spread=self.co.spread_gateway_account,
                include_member_entity_name=True))
        gw_users = set(gw_group.get('users', ()))
        for add in cere_members - gw_users:
            self.gw.add_member(pid, groupname, add)
        for rem in gw_users - cere_members:
            self.gw.remove_member(pid, groupname, rem)

    def process_dns(self):
        """Sync all DNS data with the gateway.

        In order, this function will:

          1. Look up Cerebrum subnets and VLANs
          2. Look up, compare and update VLANs in gateway
          3. Look up, compare and update subnets in gateway
          4. Look up Cerebrum hosts and IPs
          5. Look up, compare and update hosts in gateway
          6. Look up, compare and update IPs in gateway
        """
        logger.debug("Processing DNS")

        # Map subnets to projects:
        sub2ouid = dict((row['entity_id'], row['target_id']) for row in
                        self.ent.list_traits(code=self.co.trait_project_subnet)
                        if row['target_id'] in self.ouid2pid)
        sub2ouid.update(dict((row['entity_id'], row['target_id']) for row in
                             self.ent.list_traits(
                                 code=self.co.trait_project_subnet6)))
        logger.debug("Mapped %d subnets to OUs", len(sub2ouid))
        sub2pid = dict((k, self.ouid2pid[v]) for k, v in sub2ouid.iteritems()
                       if v in self.ouid2pid)
        logger.debug("Mapped %d subnets to projects", len(sub2pid))

        # Process subnets and VLANs:
        subnets, vlans = self._get_subnets_and_vlans(sub2pid)
        self._process_vlans(self.gw.list_vlans(), vlans)
        self._process_subnets(self.gw.list_subnets(), subnets, sub2ouid)

        # Mapping hosts to projects by what subnet they're on:
        hostid2pid = dict(
            (r['entity_id'], self.ouid2pid.get(r['target_id']))
            for r in self.ent.list_traits(code=self.co.trait_project_host)
            if r['target_id'] in self.ouid2pid)
        host2project = dict()
        host2ips = dict()

        def _collect(record, ip_attr):
            if record['dns_owner_id'] not in hostid2pid:
                # Host is not connected to a project, and is therefore ignored.
                logger.debug2("Host not connected to project: %s",
                              record['name'])
                return
            hostname = record['name'].rstrip('.')
            host2project[hostname] = hostid2pid[record['dns_owner_id']]
            host2ips.setdefault(hostname, set()).add(record[ip_attr])

        for row in AAAARecord.AAAARecord(self.db).list_ext():
            _collect(row, 'aaaa_ip')

        for row in ARecord.ARecord(self.db).list_ext():
            _collect(row, 'a_ip')

        logger.debug2("Mapped %d hosts to projects", len(host2project))
        logger.debug2("Mapped %d hosts with at least one IP address",
                      len(host2ips))

        # Process hosts and ips:
        self._process_hosts(self.gw.list_hosts(), host2project)
        self._process_ips(self.gw.list_ips(), host2project, host2ips)

    def _get_subnets_and_vlans(self, sub2pid):
        """Get subnets and vlans from Cerebrum.

        :param dict sub2pid: Mapping from subnet entity_id to project ou_id.

        :return tuple: A two element tuple with data from Cerebrum.

            First element: a dict that maps <ip>/<mask> to a tuple with:
                - Project ID
                - Subnet IP
                - Subnet mask
                - VLAN

            Second element: all VLANs, as a set of VLAN numbers
        """
        subnets = dict()
        vlans = set()

        def _collect(subnet, explode=lambda x: x):
            # Filters and formats a single subnet,
            # which is added to the subnet map and vlan set
            if subnet['entity_id'] not in sub2pid:
                # Skipping non-affiliated subnets
                logger.debug("Skipping non-affiliated subnet: %s",
                             subnet['entity_id'])
                return
            pid = sub2pid[subnet['entity_id']]
            if not pid:
                logger.warn("Unknown project for subnet: %s",
                            subnet['entity_id'])
                return
            key = '%s/%s' % (explode(subnet['subnet_ip']),
                             subnet['subnet_mask'])
            subnets[key] = (pid,
                            explode(subnet['subnet_ip']),
                            subnet['subnet_mask'],
                            subnet['vlan_number'], )
            vlans.add(subnet['vlan_number'])

        # ipv6 subnets
        for row in self.subnet6.search():
            _collect(row, explode=IPv6Utils.IPv6Utils.explode)

        # ipv4 subnets
        for row in self.subnet.search():
            _collect(row)

        logger.debug2("Found %s subnets for projects", len(subnets))
        logger.debug2("Found %s VLANs for projects", len(vlans))
        return subnets, vlans

    def _process_vlans(self, gw_vlans, vlans):
        """Sync given VLANs with the GW.

        :param list gw_vlans:
            The list of registered VLANs from the GW.
        :param set vlans:
            A set of all registered VLANs in Cerebrum.
        """
        processed = set()
        for gw_vlan in gw_vlans:
            vlan = gw_vlan['vlantag']
            processed.add(vlan)
            if vlan not in vlans:
                try:
                    self.gw.delete_vlan(vlan)
                except Gateway.GatewayException, e:
                    logger.warn("GatewayException deleting VLAN %s: %s",
                                vlan, e)

        for vlan in vlans:
            if vlan in processed:
                continue
            try:
                self.gw.create_vlan(vlan)
            except Gateway.GatewayException, e:
                logger.warn("GatewayException creating VLAN %s: %s",
                            vlan, e)
            else:
                processed.add(vlan)

    def _process_subnets(self, gw_subnets, subnets, sub2ouid):
        """Sync given subnets with the GW.

        :param list gw_subnets:
            The list of registered subnets from the GW.

        :param dict subnets:
            The list of registered subnets from the GW, where the subnet_ip is
            the key. For IPv6, the IP address must not be in compact format, to
            easier compare with the GW.

            Note that this comparement does not always work, as you are able to
            save

        :param dict sub2ouid:
            A mapping from each subnet's entity_id, to the entity_id of the
            project it belongs to. Subnets not affiliated with any project
            will not be given to the GW.
        """
        processed = set()
        for sub in gw_subnets:
            adr = sub['netaddr']
            try:
                pid = sub['project']
            except KeyError:
                logger.error("Missing project for address: %s", adr)
                continue

            ident = '%s/%s' % (adr, sub['prefixlen'])
            processed.add(ident)
            try:
                if ':' in adr:
                    self.subnet6.clear()
                    self.subnet6.find(ident)
                    s_id = self.subnet6.entity_id
                else:
                    self.subnet.clear()
                    self.subnet.find(ident)
                    s_id = self.subnet.entity_id
            except SubnetError:
                logger.info("Unknown subnet: %s", ident)
                self.gw.delete_subnet(pid, adr, sub['prefixlen'],
                                      sub['vlantag'])
                continue
            if ident not in subnets:
                logger.warn("Subnet flaw, probably wrong ip: %s/%s", adr,
                            sub['prefixlen'])
                # TODO: Delete subnet, or handle it manually?
                continue
            if s_id not in sub2ouid:
                logger.info("No mapping of subnet to project: %s", adr)
                self.gw.delete_subnet(pid, adr, sub['prefixlen'],
                                      sub['vlantag'])
                continue
            # TODO: check that netaddr and prefixlen is correct
        for ident, sub in subnets.iteritems():
            if ident in processed:
                continue
            logger.debug3("New subnet: %s" % (sub,))
            try:
                self.gw.create_subnet(*sub)
            except Gateway.GatewayException, e:
                logger.warn("GatewayException creating subnet: %s" % e)

    def _process_hosts(self, gw_hosts, host2project):
        """Sync given hosts with the GW.

        :param list gw_hosts:
            List of all hosts from the GW.

        :param dict host2project:
            The hosts registered in Cerebrum. Keys are hostnames, values are
            the project IDs.
        """
        processed = set()
        for host in gw_hosts:
            hostname = host['name']
            try:
                pid = host['project']
            except KeyError:
                logger.error("Missing project for host: %s", hostname)
                continue

            processed.add(hostname)
            if hostname not in host2project:
                # TODO: check the value 'expired'
                self.gw.delete_host(pid, hostname)
        for host, pid in host2project.iteritems():
            if host in processed:
                continue
            try:
                self.gw.create_host(pid, host)
            except Gateway.GatewayException, e:
                logger.warn("GatewayException creating host %s:%s: %s",
                            pid, host, e)

    def _process_ips(self, gw_ips, host2project, host2ips):
        """Sync given IPs with the GW.

        :param list gw_ips:
            List of all IP addresses registered in GW.

        :param dict host2project:
            Mapping from hostname to project ID.

        :param dict host2ips:
            All IP addresses registered in Cerebrum. The keys are the hostname,
            and the values are sets with IP addresses.
        """
        processed = set()
        for p in gw_ips:
            addr = p['addr']
            try:
                hostname = p['host']
                pid = p['project']
            except KeyError, e:
                logger.error("Missing element from GW about IP %s: %e",
                             addr, e)
                continue

            processed.add(':'.join((pid, hostname, addr)))
            if hostname not in host2project or hostname not in host2ips:
                try:
                    self.gw.delete_ip(pid, hostname, addr)
                except Gateway.GatewayException, e:
                    logger.warn("GW exception for deleting IP %s for %s: %s",
                                addr, hostname, e)
                continue
            if addr not in host2ips[hostname]:
                try:
                    self.gw.delete_ip(pid, hostname, addr)
                except Gateway.GatewayException, e:
                    logger.warn("GW exception for deleting IP %s for %s: %s",
                                addr, hostname, e)
                continue
        # Create the IP addresses that didn't exist in GW:
        for hst, addresses in host2ips.iteritems():
            try:
                pid = host2project[hst]
            except KeyError:
                logger.debug("Host not affiliated with project: %s", hst)
                continue
            for adr in addresses:
                if ':'.join((pid, hst, adr)) in processed:
                    continue
                try:
                    self.gw.create_ip(pid, hst, adr)
                except Gateway.GatewayException, e:
                    logger.warn("GW exception for new IP %s: %s", adr, e)


def main():
    """Script invocation."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-u', '--url', dest='url', metavar='URL',
        default=cereconf.TSD_GATEWAY_URL,
        help=("The full URL to the Gateway. "
              "Example: https://gw.tsd.uio.no:1234/RPC "
              "Default: cereconf.TSD_GATEWAY_URL"))
    parser.add_argument(
        '-d', '--dryrun', dest='dryrun', action='store_true', default=False,
        help=("Run the sync in dryrun. Data is retrieved from the Gateway and "
              "compared, but changes are not sent back to the gateway. "
              "Default is to commit the changes."))
    parser.add_argument(
        '-m', '--mock', dest='mock', action='store_true', default=False,
        help=("Mock the gateway by returning empty lists instead with the GW. "
              "Usable for testing the functionality locally."))
    args = parser.parse_args()

    gw_cls = Gateway.GatewayClient

    if args.mock:
        from Cerebrum.modules.tsd import GatewayMock
        gw_cls = GatewayMock.MockClient

    if args.url:
        gw = gw_cls(logger, uri=args.url, dryrun=args.dryrun)
    else:
        raise SystemExit("No url given, and no default url in cereconf")

    logger.debug("Start gw-sync against URL: %s", gw)
    p = Processor(gw, args.dryrun)
    p.process()
    logger.info("Finished gw-sync")


if __name__ == '__main__':
    main()
