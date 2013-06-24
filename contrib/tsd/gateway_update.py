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
"""Job for syncing Cerebrum data with TSD's Gateway.

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
                        Gateway, but no data is given to it.

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

        # Map persons' full names (realname)
        self.peid2name = dict((row['person_id'], row['name']) for row in
                              self.pe.search_person_names(name_variant=self.co.name_full,
                                                     source_system=self.co.system_cached))
        # Map account_id to account_name:
        self.acid2acname = dict((row['account_id'], row['name']) for row in
                                self.ac.search(spread=self.co.spread_gateway_account))

        # TODO: cache some data for efficiency

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
            except Gateway.GatewayException:
                continue

        # Add active OUs that exists in Cerebrum but not in the self.gw:
        for row in self.ou.search(filter_quarantined=True):
            if row['ou_id'] in processed_ous:
                continue
            logger.info("Unprocessed project: %s", row['ou_id'])
            self.ou.clear()
            self.ou.find(row['ou_id'])
            self.gw.create_project(self.ou.get_project_name())

    def process_project(self, pid, proj, processed_ous):
        """Process a given project retrieved from the self.gw.

        The information should be retrieved from the gateway, and is then matched
        against what exist in Cerebrum.

        """
        logger.debug("Processing project %s: %s", pid, proj)
        self.ou.clear()
        try:
            self.ou.find_by_tsd_projectname(pid)
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
        processed_ous.add(self.ou.entity_id)

    def process_project_members(self, ou, proj):
        """Sync the members of a project."""

        ce_users = dict((self.acid2acname[row['account_id']], row) for row in
                        self.ac.list_accounts_by_type(ou_id=ou.entity_id,
                                                      filter_expired=True,
                                account_spread=self.co.spread_gateway_account))
        for user in proj['users']:
            username = user['name']
            logger.debug("Process account %s: %s", username, user)
            if username not in ce_users:
                self.gw.delete_user(username)
            # TODO: check quarantines and freeze/thaw

            # TODO: update info, like realname

            del ce_users[username]

        # Create the remaining, unprocessed users:
        for username, userdata in ce_users.iteritems():

            # TODO: check quarantines first!
            self.gw.create_user(ou.get_project_name(), username, 
                                self.peid2name[userdata['person_id']],
                                # TODO: account_id != posix_UID!
                                userdata['account_id'])

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hd',
                                   ['help', 'url=', 'dryrun'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    dryrun = False
    url = None

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
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

    logger.debug("Gateway: %s", gw)
    logger.info("Start gw-sync")
    p = Processor(gw, dryrun)
    p.process_projects()
    logger.info("Finished gw-sync")

if __name__ == '__main__':
    main()