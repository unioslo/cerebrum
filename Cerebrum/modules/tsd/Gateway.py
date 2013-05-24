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
"""Gateway functionality.

TSD needs to communicate with the gateway, to tell it to open and close access
to project and project members. We do for example need to give project members
access to their project, and hosts for a project needs to set up with proper
routing. All such access is handled by the gateway.

The gateway has an xmlrpc daemon running, which we communicates with. If the
gateway returns exceptions, we can not continue our processes and should
therefor just raise exceptions instead.

"""

import xmlrpclib

import cerebrum_path
import cereconf
from Cerebrum import Errors

class GatewayClient(xmlrpclib.Server, object):
    """The client for communicating with TSD's gateway."""

    def __init__(self, logger, uri=cereconf.TSD_GATEWAY_URL, dryrun=False):
        """Sets the proper URL."""
        self.logger = logger
        self.dryrun = dryrun
        super(GatewayClient, self).__init__(uri=uri, allow_none=True)

    # TBD: Adding explicit commands here, to know what methods we should be
    # calling, but we still have the option to send them in raw.

    def list_projects(self):
        """Ask GW for a list of all its projects.

        This call is not affected by the L{dryrun} option as it makes no changes
        to the GW.

        @rtype: list
        @return: Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{name}: The project-ID
            - L{frozen}: If the project is frozen (quarantined)
            - L{created}: A DateTime for when the project got created.
            - L{expires}: A DateTime for when the project expires.

        """
        self.logger.debug("Gateway: project.list")
        return self.project.list()

    def list_users(self):
        """Ask GW for a list of all its users.

        This call is not affected by the L{dryrun} option as it makes no changes
        to the GW.

        @rtype: list
        @return: Each element in the list is a dict from the server, at the time
            containing the elements:

                TODO
            - L{name}: The username
            - L{project}: What project the user belongs to.
            - L{frozen}: If the user is frozen (quarantined)
            - L{created}: A DateTime for when the user got created.
            - L{expires}: A DateTime for when the user expires.

        """
        self.logger.debug("Gateway: user.list")
        return self.user.list()

    def list_hosts(self):
        """Ask GW for a list of all its project hosts.

        This call is not affected by the L{dryrun} option as it makes no changes
        to the GW.

        @rtype: list
        @return: Each element in the list is a dict from the server, at the time
            containing the elements:

                TODO
            - L{name}: The hostname
            - L{project}: What project the host belongs to.
            - L{frozen}: If the host is frozen (quarantined)
            - L{created}: A DateTime for when the host got created.
            - L{expires}: A DateTime for when the host expires.

        """
        self.logger.debug("Gateway: host.list")
        return self.host.list()

    def get_projects(self):
        """Get all info about all projects from the GW.

        The GW is asked for all information about the projects, hosts, users,
        subnets, vlans and anything else that is relevant to Cerebrum. The
        information is then sorted and returned in an easy-to-use format.

        @rtype: dict
        @return: The keys of the dict are the project-IDs, and each element
            contains lists with information about the project's users, hosts and
            other data.

            TODO: Describe the format.

        """
        ret = dict()
        # Fetch project info:
        for proj in self.list_projects():
            ret[proj['name']] = proj
        # Fetch user info:
        for user in self.list_users():
            # TODO: what if the user belongs to a non-existing project?
            ret[user['project']].setdefault('users', []).append(user)
        # Fetch host info:
        for host in self.list_hosts():
            ret[host['project']].setdefault('hosts', []).append(host)
        # Fetch subnet info:
        # TODO
        # Fetch vlan info:
        # TODO
        return ret

    def delete_project(self, pid):
        """Delete a given project from the GW.

        TODO: Do we have to delete all its elements explicitly? Find out.

        @type pid: string
        @param pid: The project-ID that should be deleted.

        """
        self.logger.info("Gateway: project.delete(%s)", pid)
        if self.dryrun:
            return True
        return self.project.delete({'project': pid})
