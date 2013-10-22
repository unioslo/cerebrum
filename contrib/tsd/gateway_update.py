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
"""Job for syncing Cerebrum data with TSD's Gateway (GW).

The Gateway needs information about all projects, accounts, hosts, subnets and
VLANs, to be able to let users in to the correct project. This information comes
from Cerebrum. Some of the information is sent to the Gateway e.g through bofh
commands and the import from Nettskjema, but not all information gets update
that way. An example is quarantines that gets activated or deactivated.

"""

import sys
import os
import getopt
from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.dns.Errors import SubnetError
# Parts of the DNS module raises bofhd exceptions. Need to handle this:
from Cerebrum.modules.bofhd.errors import CerebrumError as BofhdCerebrumError
from Cerebrum.modules import dns 

from Cerebrum.modules.tsd import Gateway

logger = Factory.get_logger('cronjob')

def usage(exitcode=0):
    print """
    %(doc)s 
    
    Usage: %(file)s TODO

    TODO

    --url URL           The full URL to the Gateway.
                        Example: https://gw.tsd.uio.no:1234/RPC
                        Default: cereconf.TSD_GATEWAY_URL

    -d --dryrun         Run the sync in dryrun. Data is retrieved from the
                        Gateway and compared, but changes are not sent back to
                        the gateway. Default is to commit the changes.

    --mock              Mock the gateway by returning empty lists instead of
                        talking with the GW. Usable for testing the
                        functionality locally.

    -h --help           Show this and quit.

    """ % {'doc': __doc__,
           'file': os.path.basename(sys.argv[0])}
    sys.exit(exitcode)

class Project(object):
    """Container of a project and its data.

    This is to ease the comparement of projects with the Gateway.

    """
    def __init__(self, entity_id):
        self.entity_id = entity_id
        #self.pid = TODO # ?
        # TODO: add more data

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
        self.subnet6 = dns.IPv6Subnet.IPv6Subnet(self.db)
        self.subnet = dns.Subnet.Subnet(self.db)

        # Map account_id to account_name:
        self.acid2acname = dict((row['account_id'], row['name']) for row in
                                self.ac.search(spread=self.co.spread_gateway_account))
        logger.debug2("Found %d accounts" % len(self.acid2acname))
        # Map ou_id to project id:
        self.ouid2pid = dict((row['entity_id'], row['external_id']) for row in
                self.ou.search_external_ids(entity_type=self.co.entity_ou,
                    id_type=self.co.externalid_project_id))
        logger.debug2("Found %d project IDs" % len(self.ouid2pid))

    def process(self):
        """Go through all projects in Cerebrum and compare them with the Gateway.

        If the Gateway contains mismatches, it should be updated.

        """
        gw_data = dict()
        for key, meth in (('projects', self.gw.list_projects), 
                          ('users', self.gw.list_users),
                          ('hosts', self.gw.list_hosts),
                          ('ips', self.gw.list_ips),
                          ('subnets', self.gw.list_subnets),
                          ('vlans', self.gw.list_vlans)):
            logger.debug("Getting %s from GW...", key)
            gw_data[key] = meth()
            logger.debug("Got %d entities in %s", len(gw_data[key]), key)
        self.process_projects(gw_data['projects'])
        self.process_users(gw_data['users'])
        self.process_dns(gw_data['hosts'], gw_data['subnets'], gw_data['vlans'],
                         gw_data['ips'])

    def process_projects(self, gw_projects):
        """Go through and update the projects from the GW.

        Since we should not have that many projects, maybe up to a few hundreds,
        it loops through each OU by find() and clear(). If TSD would grow larger
        in size, this script might take too long to finish, so we then might
        have to cache it.

        """
        processed = set()
        # Update existing projects:
        for proj in gw_projects:
            pid = proj['name']
            try:
                self.process_project(pid, proj)
            except Gateway.GatewayException, e:
                logger.warn("GatewayException for %s: %s" % (pid, e))
            processed.add(pid)
        # Add new OUs:
        for row in self.ou.search(filter_quarantined=True):
            self.ou.clear()
            self.ou.find(row['ou_id'])
            pid = self.ou.get_project_id()
            if pid in processed:
                continue
            self.gw.create_project(pid)

    def process_project(self, pid, proj):
        """Process a given project retrieved from the GW.

        The information should be retrieved from the gateway, and is then
        matched against what exist in Cerebrum.

        @type pid: string
        @param pid: The project ID.

        @type proj: dict
        @param proj: Contains the information about a project and all its
            elements.

        """
        logger.debug("Processing project %s: %s", pid, proj)
        self.ou.clear()
        try:
            self.ou.find_by_tsd_projectid(pid)
        except Errors.NotFoundError:
            # TODO: check if the project is marked as 'expired', so we don't
            # send this to the gw every time.
            # if proj['expires'] and proj['expires'] < DateTime.now():
            self.gw.delete_project(pid)
            return

        quars = dict((row['quarantine_type'], row) for row in
                     self.ou.get_entity_quarantine(only_active=False))
        active_quars = dict((row['quarantine_type'], row) for row in
                            self.ou.get_entity_quarantine(only_active=True))

        # Quarantines - delete, freeze and thaw
        if (quars.has_key(self.co.quarantine_project_end) and
                quars[self.co.quarantine_project_end]['start_date'] < DateTime.now()):
            self.gw.delete_project(pid)
        if len(active_quars) > 0:
            if not proj['frozen']:
                self.gw.freeze_project(pid)
        else:
            if proj['frozen']:
                self.gw.thaw_project(pid)

    def process_users(self, gw_users):
        """Sync all users with the GW."""
        processed = set()
        # Get the mapping to each project. Each user can only be part of one
        # project.
        ac2proj = dict()
        for row in self.pu.list_accounts_by_type(
                            affiliation=self.co.affiliation_project,
                            filter_expired=True,
                            account_spread=self.co.spread_ad_account):
            if ac2proj.has_key(row['account_id']):
                logger.warn("Account %s affiliated with more than one project",
                            row['account_id'])
                continue
            ac2proj[row['account_id']] = row['ou_id']

        # Update existing projects:
        for usr in gw_users:
            try:
                self.process_user(usr, ac2proj)
            except Gateway.GatewayException, e:
                logger.warn("GW exception for %s: %e" % (usr, e))
            processed.add(usr['username'])
        # Add new users:
        for row in self.pu.search(spread=self.co.spread_gateway_account):
            if row['name'] in processed:
                continue
            self.pu.clear()
            try:
                self.pu.find(row['account_id'])
            except Errors.NotFoundError:
                logger.debug("Skipping non-posix user: %s", row['account_id'])
                continue
            # Skip quarantined accounts:
            if tuple(self.pu.get_entity_quarantine(only_active=True)):
                continue
            # Skip accounts not affiliated with a project.
            pid = self.ouid2pid.get(ac2proj.get(self.pu.entity_id))
            if not pid:
                logger.debug("Skipping unaffiliated account: %s",
                        self.pu.entity_id)
                continue
            self.gw.create_user(pid, row['name'])

    def process_user(self, gw_user, ac2proj):
        """Sync a given user with the GW.

        @type gw_user: dict
        @param gw_user: The data about the user from the GW.

        @type ac2proj: dict
        @param ac2proj: A mapping from 

        """
        username = gw_user['username']
        pid = gw_user['project']
        self.pu.clear()
        try:
            self.pu.find_by_name(username)
        except Errors.NotFoundError:
            self.gw.delete_user(pid, username)
            return
        # Skip accounts not affiliated with a project.
        if not ac2proj.get(self.pu.entity_id):
            self.gw.delete_user(pid, username)
            return
        if pid != self.ouid2pid.get(ac2proj[self.pu.entity_id]):
            logger.error("Danger! Project mismatch in Cerebrum and GW for account %s" % self.pu.entity_id)
            raise Exception("Project mismatch with GW and Cerebrum")
        if self.pu.get_entity_quarantine(only_active=True):
            if not gw_user['frozen']:
                self.gw.freeze_user(pid, username)
        else:
            if gw_user['frozen']:
                self.gw.thaw_user(pid, username)

    def process_dns(self, gw_hosts, gw_subnets, gw_vlans, gw_ips):
        """Sync DNS data with the gateway.

        @type gw_hosts: list
        @param gw_hosts: All given hosts from the GW.

        @type gw_subnets: list
        @param gw_projects: All given subnets from the GW.

        @type gw_vlans: list
        @param gw_vlans: All given VLANS from the GW.

        @type gw_ips: list
        @param gw_ips: All given IP addresses from the GW.

        """
        # TODO: This method could be split into logical parts - getting too big
        dns_owner = dns.DnsOwner.DnsOwner(self.db)
        ar = dns.ARecord.ARecord(self.db)
        aaaar = dns.AAAARecord.AAAARecord(self.db)
        finder = dns.Utils.Find(self.db, cereconf.DNS_DEFAULT_ZONE)
        compress = dns.IPv6Utils.IPv6Utils.compress

        # Map subnets to projects:
        sub2ouid = dict((row['entity_id'], row['target_id']) for row in
            self.ent.list_traits(code=self.co.trait_project_subnet))
        sub2ouid.update(dict((row['entity_id'], row['target_id']) for row in
            self.ent.list_traits(code=self.co.trait_project_subnet6)))
        logger.debug("Mapped %d subnets to OUs", len(sub2ouid))
        sub2pid = dict((k, self.ouid2pid[v]) for k, v in sub2ouid.iteritems()
                       if v in self.ouid2pid)
        logger.debug("Mapped %d subnets to projects", len(sub2pid))

        # Process subnets and VLANs:
        subnets, vlans = self._get_subnets_and_vlans(sub2pid)
        self._process_vlans(gw_vlans, vlans)
        self._process_subnets(gw_subnets, subnets)

        owner2hostname = dict((r['dns_owner_id'], r['name']) for r in
                              dns_owner.search())
        # Mapping hosts to projects by what subnet they're on:
        host2project = dict()
        host2ips = dict()
        for row in aaaar.list_ext():
            adr = row['aaaa_ip']
            self.subnet6.clear()
            try:
                self.subnet6.find(adr)
            except SubnetError:
                logger.info("No found subnet for dns_owner %s",
                            row['dns_owner_id'])
                continue
            pid = sub2pid.get(self.subnet6.entity_id)
            if not pid:
                logger.debug("Subnet %s not affiliated with project",
                        self.subnet6.entity_id)
                continue
            host2project[adr] = pid
            host2ips.setdefault(owner2hostname['dns_owner_id'], set()).add(adr)
        for row in ar.list_ext():
            adr = row['a_ip']
            self.subnet.clear()
            try:
                self.subnet.find(adr)
            except SubnetError:
                logger.info("No found subnet for dns_owner %s",
                            row['dns_owner_id'])
                continue
            pid = sub2pid.get(self.subnet.entity_id)
            if not pid:
                logger.debug("Subnet %s not affiliated with project",
                        self.subnet6.entity_id)
                continue
            host2project[adr] = pid
            host2ips.setdefault(owner2hostname['dns_owner_id'], set()).add(adr)

        self._process_hosts(gw_hosts, host2project)
        self._process_ips(gw_ips, host2project, host2ips)

    def _get_subnets_and_vlans(self, sub2pid):
        """Get subnets and vlans from Cerebrum.

        @type sub2pid: dict
        @param sub2pid: Mapping from subnet's entity_id to project's ou_id.
            This is needed to be able to return the correct project ID for an 

        """
        explode = dns.IPv6Utils.IPv6Utils.explode
        subnets = dict()
        vlans = dict()
        for row in self.subnet6.search():
            if row['entity_id'] not in sub2pid:
                # Skipping non-affiliated subnets
                continue
            pid = sub2pid[row['entity_id']]
            if not pid:
                logger.warn("Unknown project for subnet: %s", row['entity_id'])
                continue
            vlans.setdefault(pid, []).append(row['vlan_number'])
            ident = '%s/%s' % (explode(row['subnet_ip']), row['subnet_mask'])
            subnets[ident] = (pid, explode(row['subnet_ip']),
                              row['subnet_mask'], row['vlan_number'])
        for row in self.subnet.search():
            if row['entity_id'] not in sub2pid:
                # Skipping non-affiliated subnets
                continue
            pid = sub2pid[row['entity_id']]
            if not pid:
                logger.warn("Unknown project for subnet: %s", row['entity_id'])
                continue
            vlans.setdefault(pid, []).append(row['vlan_number'])
            ident = '%s/%s' % (row['subnet_ip'], row['subnet_mask'])
            subnets[ident] = (pid, row['subnet_ip'], row['subnet_mask'],
                              row['vlan_number'])
        return subnets, vlans

    def _process_vlans(self, gw_vlans, vlans):
        """Sync given VLANs with the GW.

        @type gw_vlans: list
        @param gw_vlans: The list of registered VLANs from the GW.

        @type vlans: list
        @param vlans: The list of registered VLANs in Cerebrum.

        """
        processed = set()
        for gw_vlan in gw_vlans:
            pid = gw_vlan['project']
            vlan = gw_vlan['vlantag']
            processed.add(':'.join((pid, str(vlan))))
            if pid not in vlans or vlan not in vlans[pid]:
                self.gw.delete_vlan(pid, vlan)
                continue
        for pid, vlns in vlans.iteritems():
            for vln in vlns:
                if '%s:%s' % (pid, vln) in processed:
                    continue
                self.gw.create_vlan(pid, vln)

    def _process_subnets(self, gw_subnets, subnets):
        """Sync given subnets with the GW.

        @type gw_subnets: list
        @param gw_subnets: The list of registered subnets from the GW.

        @type subnets: dict
        @param subnets: The list of registered subnets from the GW, where the
            subnet_ip is the key. For IPv6, the IP address must not be in
            compact format, to easier compare with the GW.

            Note that this comparement does not always work, as you are able to
            save

        """
        processed = set()
        for sub in gw_subnets:
            adr = sub['netaddr']
            pid = sub['project']
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
                self.gw.delete_subnet(pid, adr, sub['vlantag'])
                continue
            if ident not in subnets:
                logger.warn("Subnet flaw, probably wrong ip: %s/%s", adr,
                            sub['prefixlen'])
                continue
            if s_id not in sub2ouid:
                logger.info("No mapping of subnet to project: %s", adr)
                self.gw.delete_subnet(pid, adr, sub['vlantag'])
                continue
            # TODO: check that netaddr and prefixlen is correct
        for ident, sub in subnets.iteritems():
            if ident in processed:
                continue
            self.gw.create_subnet(*sub)

    def _process_hosts(self, gw_hosts, ce_hosts):
        """Sync given hosts with the GW.

        @type gw_hosts: list
        @param gw_hosts: List of all hosts from the GW.

        @type ce_hosts: dict
        @param ce_hosts: The hosts registered in Cerebrum. Keys are hostnames,
            values are the project IDs.

        """
        processed = set()
        for host in gw_hosts:
            hostname = host['name']
            pid = host['project']
            processed.add(hostname)
            if hostname not in ce_hosts:
                # TODO: check expired
                self.gw.delete_host(pid, hostname)
        for host, pid in ce_hosts.iteritems():
            if host in processed:
                continue
            self.gw.create_host(pid, host)

    def _process_ips(self, gw_ips, host2project, host2ips):
        """Sync given IPs with the GW.

        @type gw_ips: list
        @param gw_ips: List of all IP addresses registered in GW.

        @type host2project: dict
        @param host2project: Mapping from hostname to project ID.

        @type host2ips: dict
        @param host2ips: All IP addresses registered in Cerebrum. The keys are
            the hostname, and the values are sets with IP addresses.

        """
        processed = set()
        for p in gw_ips:
            hostname = p['host']
            pid = p['project']
            addr = p['addr']
            processed.add(':'.join((pid, hostname, addr)))
            if hostname not in host2project or hostname not in host2ip:
                self.gw.delete_ip(pid, hostname, addr)
                continue
            if addr not in host2ip[hostname]:
                self.gw.delete_ip(pid, hostname, addr)
                continue
        for hst, addresses in host2ips.iteritems():
            pid = host2project[hst]
            for adr in addresses:
                if ':'.join((pid, hst, adr)) in processed:
                    continue
                self.gw.create_ip(pid, hst, adr)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hd',
                                   ['help', 'url=', 'dryrun', 'mock'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    dryrun = False
    mock = False
    url = None

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('--mock'):
            mock = True
            dryrun = True
        elif opt in ('--url',):
            url = val
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    if url:
        gw = Gateway.GatewayClient(logger, uri=url, dryrun=dryrun)
    else:
        gw = Gateway.GatewayClient(logger, dryrun=dryrun)

    if mock:
        #gw.get_projects = lambda: dict()
        logger.debug("Mocking GW")
        for t in gw.__class__.__dict__:
            if t.startswith('list_'):
                logger.debug("Mocking: %s", t)
                setattr(gw, t, lambda: list())
            elif t.startswith('get_'):
                logger.debug("Mocking: %s", t)
                setattr(gw, t, lambda: dict())

    logger.debug("Start gw-sync against URL: %s", gw)
    p = Processor(gw, dryrun)
    p.process()
    logger.info("Finished gw-sync")

if __name__ == '__main__':
    main()
