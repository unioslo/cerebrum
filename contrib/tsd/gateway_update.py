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
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
pe = Factory.get('Person')(db)
ac = Factory.get('Account')(db)



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

def process_projects(gw, dryrun):
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
    gw_projects = gw.get_projects()
    logger.debug("Got %d projects from GW", len(gw_projects))
    for pid, proj in gw_projects.iteritems():
        try:
            process_project(gw, pid, proj)
        except Gateway.GatewayException:
            continue
        processed_ous.add(ou.entity_id)

    # Add active OUs that exists in Cerebrum but not in the GW:
    for row in ou.search(filter_quarantined=True):
        if row['ou_id'] in processed_ous:
            continue
        logger.info("Unprocessed project: %s", row['ou_id'])
        ou.clear()
        ou.find(row['ou_id'])
        gw.create_project(ou.get_project_name())

def process_project(gw, pid, proj):
    """Process a given project retrieved from the GW.

    The information should be retrieved from the gateway, and is then matched
    against what exist in Cerebrum.

    """
    logger.debug("Processing project %s: %s", pid, proj)
    ou.clear()
    try:
        ou.find_by_tsd_projectname(pid)
    except Errors.NotFoundError:
        gw.delete_project(pid)
        return

    # Quarantines
    if ou.get_entity_quarantine(only_active=True):
        if not proj['frozen']:
            gw.freeze_project(pid)
    else:
        if proj['frozen']:
            gw.thaw_project(pid)

    print "Project: %s" % (pid,)
    # TODO: fix the data for each project


    return

    #
    # Cache Cerebrum-projects:
    pro2name = dict((row['name'], row['entity_id'])
                    for row in ou.search_tsd_projects())
    ous = []
    for row in ou.search(filter_quarantined=False):
        ous.append(Project(row['ou_id']))
        #print row
    # TODO: cache project-IDs:
    #for row in ou.search_name_with_language(TODO)
    logger.debug("Cached %d projects from Cerebrum", len(pro2name))




    # TODO: Go throuch list of cached Cerebrum projects, create those that was
    # not returned from GW:

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
        gw = Gateway.GatewayClient(logger, uri=url)
    else:
        gw = Gateway.GatewayClient(logger)

    logger.debug("Gateway: %s", gw)
    logger.info("Start gw-sync")
    process_projects(gw, dryrun)
    logger.info("Finished gw-sync")

if __name__ == '__main__':
    main()
