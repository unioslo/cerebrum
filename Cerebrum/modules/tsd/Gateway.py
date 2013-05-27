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

See
https://www.usit.uio.no/prosjekter/tsd20/workflows/provisioning%20-%20Cerebrum/gateway-rpc.html
for the available commands at the Gateway.

"""

import xmlrpclib

import cerebrum_path
import cereconf
from Cerebrum import Errors

class GatewayException(Exception):
    """Exception raised by the Gateway.

    This is normally xmlrpclib.Fault. The Gateway doesn't give much feedback,
    unfortunately.

    """
    pass

class GatewayClient(xmlrpclib.Server, object):
    """The client for communicating with TSD's gateway."""

    def __init__(self, logger, uri=cereconf.TSD_GATEWAY_URL, dryrun=False):
        """Sets the proper URL."""
        self.logger = logger
        self.dryrun = dryrun
        super(GatewayClient, self).__init__(uri=uri,
                                            allow_none=True)

    def __getattr__(self, name):
        """"magic method dispatcher" overrider.
        
        This is added to log and handle Faults, and since __request is
        "private", it needed to be overridden in this subclass.

        """
        return xmlrpclib._Method(self.__request, name)

    def _prettify_dict(self, data):
        """Return a "prettified", human-readable string representation of data.

        This purpose of this was to make the log easier to watch.

        """
        if len(data) == 0:
            return ''
        def prettify(d):
            return ', '.join('%s=%s' % (k, d[k]) for k in d)
        if len(data) == 1:
            return prettify(data[0])
        # Expects the data to be a tuple/list and not a dict, while the
        # elements are dicts. This is only for this Gateway, and is not the
        # behaviour of all xmlrpc servers.
        return ', '.join('(%s)' % prettify(d) for d in data)

    def __request(self, methodname, params):
        """Overriding "magic method dispatcher" for log and handling Faults.

        The gateway needs to get all its data from the first param, so it's used
        a bit special in this project.

        TODO: Might want to fix this behaviour in here? Would make it easier to
        communicate with the gateway.

        """
        # Prettify each call's log message:
        self.logger.info("Gateway call: %s(%s)", methodname,
                         self._prettify_dict(params))
        try:
            # Note that we here call a "private" method in
            # xmlrpclib.ServerProxy. Not the best behaviour, but the alternative
            # was to make an almost complete copy of ServerProxy in here, since
            # it has too many private methods and variables...
            return super(GatewayClient, self)._ServerProxy__request(methodname,
                                                                    params)
        except xmlrpclib.Fault, e:
            raise GatewayException(e)

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
        return self.host.list()

    def list_subnets(self):
        """Ask GW for a list of all its defined subnets.

        This call is not affected by the L{dryrun} option as it makes no changes
        to the GW.

        @rtype: list
        @return: Each element in the list is a dict from the server, at the time
            containing the elements:

                TODO
            - L{name}: The hostname
            - L{project}: What project the host belongs to.
              ???

        """
        return self.subnet.list()

    def list_vlans(self):
        """Ask GW for a list of all its defined VLANs.

        This call is not affected by the L{dryrun} option as it makes no changes
        to the GW.

        @rtype: list
        @return: Each element in the list is a dict from the server, at the time
            containing the elements:

                TODO
            - L{name}: The hostname
            - L{project}: What project the host belongs to.
              ???

        """
        return self.vlan.list()

    def get_projects(self):
        """Get all info about all projects from the GW.

        The GW is asked for all information about the projects, hosts, users,
        subnets, vlans and anything else that is relevant to Cerebrum. The
        information is then sorted and returned in an easy-to-use format.

        @rtype: dict
        @return: The keys of the dict are the project-IDs, and each element
            contains a dict with information about the project. Each project
            contains information about the project's users, hosts, subnets and
            vlans. Each element's keys:

                - name (string): The project ID
                - frozen (DateTime): If set, the start time for when the project
                  got, or is going to be, frozen.
                - expires (DateTime): If set, the start time for when the
                  project expires.
                - created (DateTime): The time for when the project got
                  registered in the Gateway.
                - users (list of dict with user info): The users registered for
                  the given project. See L{list_users} for the keys.
                - hosts (list of dict with host info): The hosts registered for
                  the given project. See L{list_hosts} for the keys.
                - subnets (list of dict with subnet info): The subnets
                  registered for the given project. See L{list_subnets} for the
                  keys.
                - vlans (list of dict with vlan info): The vlans registered for
                  the given project. See L{list_vlans} for the keys.

        """
        ret = dict()
        # Fetch project info:
        for proj in self.list_projects():
            # Adding empty lists of elements to make later code easier:
            proj.update({'users': [], 'hosts': [], 'subnets': [], 'vlans': []})
            ret[proj['name']] = proj

        # Fetch user info:
        for user in self.list_users():
            # TODO: what if the user belongs to a non-existing project?
            ret[user['project']]['users'].append(user)
        # Fetch host info:
        for host in self.list_hosts():
            ret[host['project']]['hosts'].append(host)
        # TODO: Add these when the Gateway does not raise Faults:
        # Fetch subnet info:
        #for subn in self.list_subnets():
        #    ret[subn['project']]['subnets'].append(subn)
        # Fetch vlan info:
        #for vlan in self.list_vlans():
        #    ret[vlan['project']]['vlans'].append(vlan)
        return ret

    def create_project(self, pid):
        """Create a new project in the GW.

        @type pid: string
        @param pid: The project ID.

        """
        self.logger.info("Creating project: %s", pid)
        if self.dryrun:
            return True
        return self.project.create({'project': pid})

    def delete_project(self, pid):
        """Delete a given project from the GW.

        TODO: Do we have to delete all its elements explicitly? Find out.

        @type pid: string
        @param pid: The project-ID that should be deleted.

        """
        self.logger.info("Deleting project: %s", pid)
        if self.dryrun:
            return True
        return self.project.delete({'project': pid})

    def freeze_project(self, pid, when=None):
        """Freeze a project in the GW.

        @type pid: string
        @param pid: The project ID.

        @type when: DateTime
        @param when: When the freeze should happen. Defaults to now if not set.

        """
        self.logger.info("Freezing project: %s", pid)
        if self.dryrun:
            return True
        params = {'project': pid}
        # TODO: 'when' not implemented yet!
        return self.project.freeze({'project': pid})

    def thaw_project(self, pid):
        """Unfreeze a project in the GW.

        @type pid: string
        @param pid: The project ID.

        """
        self.logger.info("Thawing project: %s", pid)
        if self.dryrun:
            return True
        return self.project.thaw({'project': pid})

    def create_user(self, pid, username, realname, uid):
        """Create a user in the GW.

        @type pid: string
        @param pid: The project ID.

        @type username: string
        @param username: The username of the user.

        @type realname: string
        @param realname: The name of the user. It has no practical significance
            for the gateway.

        @type uid: int
        @param uid: The posix UID of the user.

        """
        self.logger.info("Creating user: %s", username)
        if self.dryrun:
            return True
        return self.user.create({'project': pid, 'username': username,
                                 'realname': realname, 'uid': uid})


