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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
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
        self.ou = Factory.get('OU')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pu = Factory.get('PosixUser')(self.db)

        # Map account_id to account_name:
        self.acid2acname = dict((row['account_id'], row['name']) for row in
                                self.ac.search(spread=self.co.spread_gateway_account))
        logger.debug2("Found %d accounts" % len(self.acid2acname))

    def process_projects(self):
        """Go through all projects in Cerebrum and compare them with the Gateway.

        If the Gateway contains mismatches, it should be updated.

        """
        # The list of OUs that was found at the GW. Used to be able to create those
        # that doesn't exist.
        processed_ous = set()

        # Since we should not have that many projects, maybe up to a few thousand,
        # it loops through each OU by find() and clear(). If TSD would grow larger
        # in size, this script might take too long to finish, so we then might have
        # to cache it.
        gw_projects = self.gw.get_projects()
        logger.debug("Got %d projects from self.gw", len(gw_projects))
        for pid, proj in gw_projects.iteritems():
            try:
                self.process_project(pid, proj, processed_ous)
            except Gateway.GatewayException, e:
                logger.warn("GatewayException for %s: %s" % (pid, proj))
        # Add active OUs that exists in Cerebrum but not in the GW:
        for row in self.ou.search(filter_quarantined=True):
            if row['ou_id'] in processed_ous:
                continue
            self.ou.clear()
            self.ou.find(row['ou_id'])
            pid = self.ou.get_project_id()
            self.gw.create_project(pid)
            logger.info("New project: %s", pid)
            # TODO: process the project, but need to get the info first
            #self.process_project(self.ou.get_project_id(), 
        # Sync all hosts:
        self.process_dns(gw_projects)

    def process_project(self, pid, proj, processed_ous):
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
            self.gw.delete_project(pid)
            return

        quars = dict((row['quarantine_type'], row) for row in
                     self.ou.get_entity_quarantine(only_active=False))
        active_quars = dict((row['quarantine_type'], row) for row in
                            self.ou.get_entity_quarantine(only_active=True))

        # Quarantines
        if len(active_quars) > 0:
            if not proj['frozen']:
                self.gw.freeze_project(pid)
        else:
            if proj['frozen']:
                self.gw.thaw_project(pid)

        # Delete expired projects. TODO: or just freeze them, waiting for the
        # permanent deletion?
        if quars.has_key(self.co.quarantine_project_end):
            if quars[self.co.quarantine_project_end]['start_date'] < DateTime.now():
                self.gw.delete_project(pid)

        self.process_project_members(self.ou, proj)
        #self.process_project_hosts(self.ou, proj)
        processed_ous.add(self.ou.entity_id)

    def process_project_members(self, ou, proj):
        """Sync the members of a project."""
        pid = ou.get_project_id()
        ce_users = dict((self.acid2acname[row['account_id']], row) for row in
                        self.pu.list_accounts_by_type(ou_id=ou.entity_id,
                                                      filter_expired=False,
                                account_spread=self.co.spread_gateway_account))
        # Remove accounts not registered in Cerebrum:
        for user in proj['users']:
            username = user['username']
            if username not in ce_users:
                logger.debug("Removing account %s: %s", username, user)
                self.gw.delete_user(pid, username)
        # Update the rest of the accounts:
        for username, userdata in ce_users.iteritems():
            self.pu.clear()
            self.pu.find(userdata['account_id'])
            is_frozen = bool(tuple(self.pu.get_entity_quarantine(
                only_active=True)))

            if username not in proj['users']:
                if is_frozen:
                    logger.info("Skipping unregistered but frozen account: %s",
                            username)
                    continue
                self.gw.create_user(ou.get_project_id(), username, pu.posix_uid)
            gwuserdata = proj['users'][username]
            if is_frozen:
                if not gwuserdata['frozen']:
                    self.gw.freeze_user(pid, username)
            else:
                if gwuserdata['frozen']:
                    self.gw.thaw_user(pid, username)
            # Updating realname not implemented, as it's not used.

    def process_dns(self, gw_projects):
        """Sync all hosts to the gateway.

        @type gw_projects: dict
        @param gw_projects: All info about the projects, from the GW.

        """
        # Hosts:
        #
        # TODO
        # Subnets and vlans
        gw_subnets = dict()
        #for proj in gw_projects.itervalues():
        #    gw_subnets[

        #ret = []
        ## IPv6:
        #subnet6 = IPv6Subnet.IPv6Subnet(self.db)
        #compress = IPv6Utils.IPv6Utils.compress
        #for row in subnet6.search():
        #    ret.append({
        #        'subnet': '%s/%s' % (compress(row['subnet_ip']),
        #                             row['subnet_mask']),
        #        'vlan_number': str(row['vlan_number']),
        #        'description': row['description']})
        ## IPv4:
        #subnet = Subnet.Subnet(self.db)
        #for row in subnet.search():
        #    ret.append({
        #        'subnet': '%s/%s' % (row['subnet_ip'], row['subnet_mask']),
        #        'vlan_number': str(row['vlan_number']),
        #        'description': row['description']})
        #self.logger.debug("Found %d subnets", len(ret))
        ## Sort by subnet
        #return sorted(ret, key=lambda x: x['subnet'])

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
                setattr(gw, t, lambda: list())
            elif t.startswith('get_'):
                setattr(gw, t, lambda: dict())

    logger.debug("Gateway: %s", gw)
    logger.info("Start gw-sync")
    p = Processor(gw, dryrun)
    p.process_projects()
    logger.info("Finished gw-sync")

if __name__ == '__main__':
    main()
