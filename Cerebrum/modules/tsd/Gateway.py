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
"""Functionality for communicating with the TSD gateway.

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
from __future__ import unicode_literals

import xmlrpclib
import mx

import six

import cereconf


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

        This purpose of this was to make the log easier to watch. Some of the
        more sensitive parameters, like OTP keys, are stripped away.

        :param iterable data:
            The parameters that should be sent to the GW.

        :return string: A log readable string of all the parameters.
        """
        if len(data) == 0:
            return ''

        def prettify(d):
            ret = []
            for k, v in d.iteritems():
                # Expand this list with more parameters that should be
                # considered secret:
                if k in ('otpuri', 'otpkey'):
                    v = '**********'
                ret.append('%s=%s' % (k, v))
            return ', '.join(ret)

        if len(data) == 1:
            return prettify(data[0])
        # Expects the data to be a tuple/list and not a dict, while the
        # elements are dicts. This is only for this Gateway, and is not the
        # behaviour of all xmlrpc servers.
        return ', '.join('(%s)' % prettify(d) for d in data)

    def __request(self, methodname, params):
        """Overriding "magic method dispatcher" for log and handling Faults.

        The gateway needs to get all its data from the first param, so it's
        used a bit special in this project.

        TODO: Might want to fix this behaviour in here? Would make it easier to
        communicate with the gateway.
        """
        # Prettify each call's log message:
        self.logger.debug("Gateway call: %s(%s)", methodname,
                          self._prettify_dict(params))
        try:
            # Note that we here call a "private" method in
            # xmlrpclib.ServerProxy. Not the best behaviour, but the
            # alternative was to make an almost complete copy of ServerProxy
            # in here, since it has too many private methods and variables...
            return self.__typecast(
                super(GatewayClient, self)._ServerProxy__request(
                    methodname, self.__typecast(params)))
        except xmlrpclib.Fault, e:
            raise GatewayException(e)

    def __typecast(self, data):
        """Typecast specific object types.

        Typecasts:
        xmlrpclib.DateTime → mx.DateTime.DateTime
        mx.DateTime.DateTime → xmlrpclib.DateTime

        :param object data: The data to typecast.

        :return object: The typecasted data.
        """
        # TODO: Make me configurable!

        def cast_elements(elms):
            collect = []
            for elm in data:
                collect.append(self.__typecast(elm))
            return collect

        if isinstance(data, list):
            return cast_elements(data)
        elif isinstance(data, tuple):
            return tuple(cast_elements(data))
        elif isinstance(data, dict):
            collect = []
            for k, v in data.items():
                collect.append((k, self.__typecast(v)))
            return dict(collect)
        elif isinstance(data, xmlrpclib.DateTime):
            return mx.DateTime.strptime(data.value, "%Y%m%dT%H:%M:%S")
        elif isinstance(data, mx.DateTime.DateTimeType):
            return xmlrpclib.DateTime(data)
        else:
            return data

    # List methods

    def list_projects(self):
        """Ask GW for a list of all its projects.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{name}: The project-ID
            - L{frozen}: If the project is frozen (quarantined)
            - L{created}: A DateTime for when the project got created.
            - L{expires}: A DateTime for when the project expires.
        """
        return self.project.list()

    def list_users(self):
        """Ask GW for a list of all its users.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{username} (string): The username
            - L{project} (string): The project ID the user belongs to.
            - L{frozen} (DateTime): If, and when, the user gets quarantined.
            - L{created} (DateTime): When the user got created.
            - L{expires} (DateTime): When the user expires.
        """
        return self.user.list()

    def list_groups(self):
        """Ask GW for a list of all its groups.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{groupname} (string): The groupname
            - L{project} (string): The project ID the group belongs to.
            - L{frozen} (DateTime): If, and when, the user gets quarantined.
            - L{created} (DateTime): When the user got created.
            - L{expires} (DateTime): When the user expires.

            TODO: other data?
        """
        return self.group.list()

    def list_hosts(self):
        """Ask GW for a list of all its project hosts.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{name} (string): The hostname, in FQDN format.
            - L{project} (string): What project the host belongs to.
            - L{frozen} (DateTime): If the host is frozen (quarantined)
            - L{created} (DateTime): A DateTime for when the host got created.
            - L{expires} (DateTime): A DateTime for when the host expires.
        """
        return self.host.list()

    def list_subnets(self):
        """Ask GW for a list of all its defined subnets.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{project} (string): What project the host belongs to.
            - L{netaddr} (string): The subnet address.
            - L{prefixlen} (int): The prefix length for the subnet.
            - L{vlantag} (int): The VLAN tag for the subnet.
            - L{created} (DateTime): When the subnet was created.

            Note that the addresses could both be returned in compact and
            verbose format, you must handle both kinds! TODO: Compact the
            addresses here, before they get returned!
        """
        return self.subnet.list()

    def list_ips(self):
        """Ask GW for a list of all defined IP addresses.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{host} (string): The hostname, in FQDN format.
            - L{project} (string): What project the host belongs to.
            - L{addr} (string): The network address, in IPv4 or IPv6 format.
                                You must expect both full and compact format of
                                IPv6 addresses.

            Note that the addresses could both be returned in compact and
            verbose format, expect both types.
        """
        return self.ip.list()

    def list_vlans(self):
        """Ask GW for a list of all its defined VLANs.

        This call is not affected by the L{dryrun} option as it makes no
        changes to the GW.

        :return list:
            Each element in the list is a dict from the server, at the time
            containing the elements:

            - L{vlantag} (int): The VLAN tag.
            - L{created} (DateTime): When the VLAN was created.
        """
        return self.vlan.list()

    def get_projects(self):
        """Get all info about all projects from the GW.

        The GW is asked for all information about the projects, hosts, users,
        subnets, vlans and anything else that is relevant to Cerebrum. The
        information is then sorted and returned in an easy-to-use format.

        :return dict:
            The keys of the dict are the project-IDs, and each element contains
            a dict with information about the project. Each project contains
            information about the project's users, hosts, subnets and vlans.
            Each element's keys:

                - name (string): The project ID
                - frozen (DateTime): If set, the start time for when the
                  project got, or is going to be, frozen.
                - expires (DateTime): If set, the start time for when the
                  project expires.
                - created (DateTime): The time for when the project got
                  registered in the Gateway.
                - users (list of dict with user info): The users registered for
                  the given project. See L{list_users} for the keys.
                - groups (list of dict with group info): The groups registered
                  for the given project. See L{list_groups} for the keys.
                - hosts (list of dict with host info): The hosts registered for
                  the given project. See L{list_hosts} for the keys.
                - subnets (list of dict with subnet info): The subnets
                  registered for the given project. See L{list_subnets} for the
                  keys.
        """
        ret = dict()
        # Fetch project info:
        for proj in self.list_projects():
            # Adding empty lists of elements to make later code easier:
            proj.update({'users': [], 'hosts': [], 'subnets': [], 'vlans': []})
            ret[proj['name']] = proj

        # Fetch user info:
        for user in self.list_users():
            ret[user['project']]['users'].append(user)
        # Fetch group info:
        for group in self.list_groups():
            ret[group['project']]['groups'].append(group)
        # Fetch host info:
        for host in self.list_hosts():
            ret[host['project']]['hosts'].append(host)
        # Fetch subnet info:
        for subn in self.list_subnets():
            ret[subn['project']]['subnets'].append(subn)
        return ret

    # Project methods

    def create_project(self, pid, expire_date=None):
        """Create a new project in the GW.

        :param string pid: The project ID.
        :param mx.DateTime.DateTime expire_date: The projects expire date.
        """
        self.logger.info("Creating project: %s", pid)
        if self.dryrun:
            return True
        return self.project.create({'project': pid, 'expires': expire_date})

    def delete_project(self, pid):
        """Delete a given project from the GW.

        By deleting a given project, the GW will automatically delete the
        corresponding data, like users, hosts and subnets.

        :param string pid: The project-ID that should be deleted.
        """
        self.logger.info("Deleting project: %s", pid)
        if self.dryrun:
            return True
        return self.project.delete({'project': pid})

    def expire_project(self, pid, expire_date=None):
        """Set expire-date on project.

        :param string pid: The project identifier.
        :param mx.DateTime.DateTime expire_date: The projects expire date.
        """
        self.logger.info("Setting expire date %s on project: %s",
                         pid, expire_date)
        if self.dryrun:
            return True
        return self.project.expire({'project': pid, 'when': expire_date})

    def freeze_project(self, pid, when=None):
        """Freeze a project in the GW.

        :param string pid: The project ID.

        :param mx.DateTime.DateTime when:
            When the freeze should happen. Defaults to now if not set.
        """
        self.logger.info("Freezing project: %s", pid)
        if self.dryrun:
            return True
        params = {'project': pid}
        if when is not None:
            params['when'] = when
        return self.project.freeze(params)

    def thaw_project(self, pid):
        """Unfreeze a project in the GW.

        :param string pid: The project ID.
        """
        self.logger.info("Thawing project: %s", pid)
        if self.dryrun:
            return True
        return self.project.thaw({'project': pid})

    # User methods
    def create_user(self, pid, username, uid, realname=None, expire_date=None):
        """Create a user in the GW.

        :param string pid:
            The project ID.

        :param string username:
            The username of the user.

        :param int uid:
            The posix UID of the user.

        :param string realname:
            The name of the user. It has no practical significance for the
            gateway. Must not contain colons!

        :param mx.DateTime.DateTime expire_date: The expiry-date for the user.
        """
        self.logger.info("Creating user: %s", username)
        params = {'project': pid,
                  'username': username,
                  'uid': uid,
                  'expires': expire_date}
        if realname:
            if ':' in realname:
                self.logger.warn("Realname for %s contains colons!", username)
            else:
                params['realname'] = realname
        if self.dryrun:
            return True
        return self.user.create(params)

    def expire_user(self, pid, username, expire_date=None):
        """Set expire-date on the user in the Gateway.

        :param string pid:
            The project ID.

        :param string username:
            The username of the user.

        :param mx.DateTime.DateTime expire_date: The expire date of the user.
        """
        self.logger.info("Setting expire date for %s to %s",
                         username,
                         expire_date)
        if self.dryrun:
            return True
        return self.user.expire({'project': pid,
                                 'username': username,
                                 'when': expire_date})

    def delete_user(self, pid, username):
        """Delete a user from the GW.

        :param string pid: The project ID.

        :param string username: The username of the user.
        """
        self.logger.info("Deleting user: %s", username)
        params = {'project': pid, 'username': username}
        if self.dryrun:
            return True
        return self.user.delete(params)

    def freeze_user(self, pid, username, when=None):
        """Freeze an existing user in the GW.

        :param string pid:
            The project ID.

        :param string username:
            The username of the account

        :param mx.DateTime.DateTime when:
            When the freeze should happen. Defaults to now if not set.

        :return bool: If the GW accepted the call.
        """
        self.logger.info("Freezing account: %s", username)
        params = {'project': pid, 'username': username}
        if self.dryrun:
            return True
        if when is not None:
            params['when'] = when
        return self.user.freeze(params)

    def thaw_user(self, pid, username):
        """Unfreeze (thaw) a user in the GW.

        :param string pid: The project ID.

        :param string username: The username of the account
        """
        self.logger.info("Thawing user: %s", username)
        params = {'project': pid, 'username': username}
        if self.dryrun:
            return True
        return self.user.thaw(params)

    def user_otp(self, pid, username, otpuri):
        """Send a new OTP key for an account to the GW.

        :param string pid:
            The project ID.

        :param string username:
            The username of the account

        :param string otpuri:
            The OTP key to send, formatted in the proper URI format.
        """
        self.logger.info("New OTP key for user: %s", username)
        params = {'project': pid, 'username': username, 'otpuri': otpuri}
        if self.dryrun:
            return True
        return self.user.otp.setkey(params)

    # Group methods

    def create_group(self, pid, groupname, gid):
        """Create a group in the GW.

        :param string pid:
            The project ID where the group belongs.

        :param string groupname:
            The groupname of the group.

        :type gid: string or int
        :param gid:
            The POSIX GID of the group.
        """
        self.logger.info("Creating group: %s (%s)", groupname, pid)
        params = {'project': pid, 'groupname': groupname, 'gid': gid}
        if self.dryrun:
            return True
        return self.group.create(params)

    def delete_group(self, pid, groupname):
        """Delete a group from the GW.

        :param string pid: The project ID.

        :param string groupname: The groupname of the group.
        """
        self.logger.info("Deleting group: %s (%s)", groupname, pid)
        params = {'project': pid, 'groupname': groupname}
        if self.dryrun:
            return True
        return self.group.delete(params)

    def add_member(self, pid, groupname, membername):
        """Add a member to a group in the GW.

        :param string pid:
            The project ID for where the group belongs.

        :param string groupname:
            The name of the target group, for which the member should be added
            to. Must exist in the GW on beforehand.

        :param string membername:
            The identifier of the member. For users this would be the
            username. The member must exist in the GW on beforehand.

            TODO: Does the GW accept other member types, like groups?
        """
        self.logger.info("Adding member to group %s: %s", groupname,
                         membername)
        params = {'project': pid,
                  'groupname': groupname,
                  'username': membername,
                  }
        if self.dryrun:
            return True
        return self.group.user.add(params)

    def remove_member(self, pid, groupname, membername):
        """Remove a member from a group in the GW.

        :param string pid:
            The project ID for where the group belongs.

        :param string groupname:
            The name of the target group, for which the member should be
            removed from. The group must exist in the GW on beforehand.

        :param string membername:
            The identifier of the member. For users this would be the
            username. The member must exist in the GW on beforehand, and for
            the method to succeed the entity must already be a member of the
            group.

            TODO: Does the GW accept other member types, like groups?

        :raise GatewayException:
            Various situations could trigger an exception from the GW, like:

            - The group does not exist in the GW.
            - The member does not exist in the GW.
            - The member is not a member of the group, and can therefore not
              be removed.
            - Unknown errors.
        """
        self.logger.info("Removing member from group %s: %s", groupname,
                         membername)
        params = {'project': pid,
                  'groupname': groupname,
                  'username': membername,
                  }
        if self.dryrun:
            return True
        return self.group.user.remove(params)

    # Host methods
    def create_host(self, pid, fqdn):
        """Create a new host in the GW.

        :param string pid:
            The project ID.

        :param string fqdn:
            The fully qualified domain name, and not the cname.
        """
        self.logger.info("Create host: %s", fqdn)
        params = {'project': pid, 'hostname': fqdn}
        if self.dryrun:
            return True
        return self.host.create(params)

    def delete_host(self, pid, fqdn):
        """Delete the given host from the GW.

        :param string pid:
            The project ID.

        :param string fqdn:
            The fully qualified domain name, not the cname.
        """
        self.logger.info("Delete host: %s", fqdn)
        params = {'project': pid, 'hostname': fqdn}
        if self.dryrun:
            return True
        return self.host.delete(params)

    def create_ip(self, pid, fqdn, ipadr, mac=None):
        """Give a host an IP address in the GW.

        :param string pid:
            The project ID.

        :param string fqdn:
            The fully qualified domain name, not the cname.

        :param string ipadr:
            The IP address for the host.

        :param string mac:
            The MAC address for the host.
        """
        self.logger.info("Add IP addr for %s: %s", fqdn, ipadr)
        params = {'project': pid, 'hostname': fqdn, 'ip': ipadr, 'mac': mac}
        if self.dryrun:
            return True
        return self.host.ip.add(params)

    def delete_ip(self, pid, fqdn, ipadr):
        """Delete the given IP address from the host in the GW.

        :param string pid:
            The project ID.

        :param string fqdn:
            The fully qualified domain name, not the cname.

        :param string ipadr:
            The IP address to remove.
        """
        self.logger.info("Delete IP addr for %s: %s", fqdn, ipadr)
        params = {'project': pid, 'hostname': fqdn, 'ip': ipadr}
        if self.dryrun:
            return True
        return self.host.ip.delete(params)

    # Subnet methods
    def create_subnet(self, pid, netaddr, prefixlen, vlan):
        """Send a subnet to the GW.

        :param string pid:
            The project ID.

        :param string netaddr:
            The network address for the subnet. Both IPv4 and IPv6 is accepted.
            Note: Do not compact IPv6 addresses, the full, verbose address must
            be given.

        :type prefixlen: str or int
        :param prefixlen:
            The prefix length of the subnet. Must be more than 0 and lower than
            max of the IP version (32 for IPv4).

        :type vlan: str or int
        :param vlan:
            The VLAN number for the project.
        """
        self.logger.info("Creating subnet for %s: %s/%s, vlan: %s",
                         pid,
                         netaddr,
                         prefixlen,
                         vlan)
        params = {'netaddr': netaddr,
                  'prefixlen': prefixlen,
                  'vlantag': six.text_type(vlan),
                  'project': pid}
        if self.dryrun:
            return True
        return self.subnet.create(params)

    def delete_subnet(self, pid, netaddr, prefixlen, vlan):
        """Remove a VLAN from the GW.

        :param string pid:
            The project ID.

        :param string netaddr:
            The network address for the subnet. Both IPv4 and IPv6 is accepted.

        :type vlan: str or int
        :param vlan:
            The VLAN tag for the subnet.
        """
        self.logger.info("Delete subnet for %s: %s", pid, netaddr)
        params = {'netaddr': netaddr,
                  'project': pid,
                  'vlantag': vlan,
                  'prefixlen': prefixlen}
        if self.dryrun:
            return True
        return self.subnet.delete(params)

    # VLAN methods
    def create_vlan(self, vlan):
        """Send a VLAN to the GW.

        :type vlan: string or int
        :param vlan: The VLAN number for the project.
        """
        self.logger.info("Creating VLAN %s", vlan)
        params = {'vlantag': six.text_type(vlan), }
        if self.dryrun:
            # TODO: What does vlan.create return on success?
            return True
        return self.vlan.create(params)

    def delete_vlan(self, vlan):
        """Remove a VLAN from the GW.

        :type vlan: string or int
        :param vlan: The VLAN number for the project.
        """
        self.logger.info("Delete VLAN %s", vlan)
        params = {'vlantag': six.text_type(vlan), }
        if self.dryrun:
            # TODO: What does vlan.delete return on success?
            return True
        return self.vlan.delete(params)
