#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2018 University of Oslo, Norway
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
"""
Mock Gateway Client for TSD.

This client can be used as a replacement for the .Gateway.GatewayClient and an
actual gateway when testing code that needs to communicate with the TSD
gateway.
"""
from __future__ import unicode_literals

import six

import cereconf

from mx import DateTime
from .Gateway import GatewayClient
from .Gateway import GatewayException as Err


@six.python_2_unicode_compatible
class MockClient(GatewayClient):
    """Mock client for testing integration with the TSD gateway."""

    def __init__(self, logger, uri=cereconf.TSD_GATEWAY_URL, dryrun=False):
        """Sets the proper URL."""
        self.logger = logger
        self.uri = uri
        self.dryrun = dryrun

        # Simplified internal representation of the gateway objects.
        # Each object is a dict, as returned from the gateway
        # See the appropriate create_* function to see how each object should
        # look.
        self._projects = list()
        self._users = list()
        self._groups = list()
        self._hosts = list()
        self._subnets = list()
        self._ips = list()
        self._vlans = list()

        # Add some pre-existing data to the gateway
        self.setup_demo_values()

    def __getattr__(self, name):
        """Used to fetch xmlrpc methods."""
        raise AttributeError("Mock client has no attribute '%s'" % name)

    def __request(self, methodname, params):
        """Used to call xmlrpc methods."""
        raise NotImplementedError("Mock client has no request method!")

    def __repr__(self):
        """The parent __repr__ requires that __init__ was called."""
        return "MockClient(%r, uri=%r, dryrun=%r)" % (self.logger,
                                                      self.uri,
                                                      self.dryrun)

    def __str__(self):
        """The parent __str__ requires that __init__ was called."""
        return "<Mock Proxy for %s>" % self.uri

    def _get_project_idx(self, pid):
        """Get list index of project in cache."""
        for idx, p in enumerate(self._projects):
            if p['name'] == pid:
                return idx
        raise Err("No project %s" % (pid))

    def _get_user_idx(self, uname, pid=None):
        """Get list index of user in cache."""
        for idx, u in enumerate(self._users):
            if u['username'] == uname and (pid is None or u['project'] == pid):
                return idx
        raise Err("No user %s (in project %s)" % (uname, pid))

    def _get_group_idx(self, gname, pid):
        """Get list index of group in cache."""
        for idx, g in enumerate(self._groups):
            if g['groupname'] == gname and g['project'] == pid:
                return idx
        raise Err("No group %s in project %s" % (gname, pid))

    def _get_host_idx(self, hname, pid):
        """Get list index of host in cache."""
        for idx, h in enumerate(self._hosts):
            if h['name'] == hname and h['project'] == pid:
                return idx
        raise Err("No host %s in project %s" % (hname, pid))

    def _get_ip_idx(self, hname, addr, pid):
        """Get list index of ip in cache."""
        for idx, ip in enumerate(self._ips):
            if (ip['host'] == hname and ip['addr'] == addr and
                    ip['project'] == pid):
                return idx
        raise Err("No host %s with ip %s in project %s" % (hname, addr, pid))

    def _get_subnet_idx(self, addr, pfx, vlan, pid):
        """Get list index of subnet in cache."""
        for idx, sub in enumerate(self._subnets):
            if (sub['project'] == pid and sub['netaddr'] == addr and
                    sub['prefixlen'] == pfx and sub['vlantag'] == vlan):
                return idx
        raise Err("No subnet %s/%s in project %s with vlan %s" % (
            addr, pfx, pid, vlan))

    def _get_vlan_idx(self, vlan):
        """Get list index of vlan in cache."""
        for idx, v in enumerate(self._vlans):
            if v['vlantag'] == vlan:
                return idx
        raise Err("No VLAN %s" % vlan)

    def list_projects(self):
        """See .Gateway.GatewayClient."""
        return self._projects

    def list_users(self):
        """See .Gateway.GatewayClient."""
        return self._users

    def list_groups(self):
        """See .Gateway.GatewayClient."""
        return self._groups

    def list_hosts(self):
        """See .Gateway.GatewayClient."""
        return self._hosts

    def list_subnets(self):
        """See .Gateway.GatewayClient."""
        return self._subnets

    def list_ips(self):
        """See .Gateway.GatewayClient."""
        return self._ips

    def list_vlans(self):
        """See .Gateway.GatewayClient."""
        return self._vlans

    def create_project(self, pid):
        """See .Gateway.GatewayClient."""
        self.logger.info("Creating project: %s", pid)
        try:
            self._get_project_idx(pid)
        except Err:
            pass
        else:
            raise Err("Project %s exists" % pid)

        p = {'frozen': None, 'expires': DateTime.now()+10,
             'name': pid, 'created': DateTime.now(), }
        self._projects.append(p)
        return p

    def delete_project(self, pid):
        """See .Gateway.GatewayClient."""
        self.logger.info("Deleting project: %s", pid)
        idx = self._get_project_idx(pid)
        # TODO: everything related to project
        del self._projects[idx]
        return

    def freeze_project(self, pid, when=None):
        """See .Gateway.GatewayClient."""
        self.logger.info("Freezing project: %s", pid)
        idx = self._get_project_idx(pid)
        if self._projects[idx]['frozen']:
            raise Err("Project already frozen")
        self._projects[idx]['frozen'] = DateTime.now()
        return self._projects[idx]

    def thaw_project(self, pid):
        """See .Gateway.GatewayClient."""
        self.logger.info("Thawing project: %s", pid)
        idx = self._get_project_idx(pid)
        if not self._projects[idx]['frozen']:
            raise Err("Project not frozen")
        self._projects[idx]['frozen'] = None
        return self._projects[idx]

    # User methods
    def create_user(self, pid, username, uid, realname=None):
        """See .Gateway.GatewayClient."""
        self.logger.info("Creating user: %s", username)
        self._get_project_idx(pid)
        try:
            self._get_user_idx(username, pid)
        except Err:
            pass
        else:
            raise Err("User %s exists in project %s" % (username, pid))

        n = {'username': username, 'created': DateTime.now(),
             'frozen': None, 'expires': DateTime.now()+10,
             'project': pid, 'groups': []}
        self._users.append(n)
        return n

    def delete_user(self, pid, username):
        """See .Gateway.GatewayClient."""
        self._get_project_idx(pid)
        idx = self._get_user_idx(username, pid)
        # TODO: remove group memberships, hosts, etc...
        del self._users[idx]
        return {}

    def freeze_user(self, pid, username, when=None):
        """See .Gateway.GatewayClient."""
        self.logger.info("Freezing account: %s", username)
        self._get_project_idx(pid)
        idx = self._get_user_idx(username, pid)
        if self._users[idx]['frozen']:
            raise Err("User already frozen")
        self._users[idx]['frozen'] = DateTime.now()
        return self._users[idx]

    def thaw_user(self, pid, username):
        """See .Gateway.GatewayClient."""
        self.logger.info("Thawing user: %s", username)
        self._get_project_idx(pid)
        idx = self._get_user_idx(username, pid)
        if not self._users[idx]['frozen']:
            raise Err("User not frozen")
        self._users[idx]['frozen'] = None
        return self._users[idx]

    def user_otp(self, pid, username, otpuri):
        """See .Gateway.GatewayClient."""
        self.logger.info("New OTP key for user: %s", username)
        self._get_project_idx(pid)
        idx = self._get_user_idx(username, pid)
        self._users[idx]['otpuri'] = otpuri
        return self._users[idx]

    # Group methods
    def create_group(self, pid, groupname, gid):
        """See .Gateway.GatewayClient."""
        self.logger.info("Creating group: %s (%s)", groupname, pid)
        self._get_project_idx(pid)
        try:
            self._get_group_idx(groupname, pid)
        except Err:
            pass
        else:
            raise Err("Group %s exists in project %s" % (groupname, pid))

        n = {'project': pid, 'groupname': groupname,
             'users': [], 'created': DateTime.now(), }
        self._groups.append(n)
        return n

    def delete_group(self, pid, groupname):
        """See .Gateway.GatewayClient."""
        self.logger.info("Deleting group: %s (%s)", groupname, pid)
        idx = self._get_group_idx(groupname, pid)
        # TODO: remove memberships from user dicts
        del self._groups[idx]
        return

    def add_member(self, pid, groupname, membername):
        """See .Gateway.GatewayClient."""
        self.logger.info("Adding member to group %s: %s", groupname,
                         membername)
        self._get_project_idx(pid)
        gidx = self._get_group_idx(groupname, pid)
        uidx = self._get_user_idx(membername)

        self._groups[gidx]['users'].append(membername)
        self._users[uidx]['groups'].append(groupname)
        return self._groups[gidx]

    def remove_member(self, pid, groupname, membername):
        """See .Gateway.GatewayClient."""
        self.logger.info("Removing member from group %s: %s",
                         groupname, membername)
        self._get_project_idx(pid)
        gidx = self._get_group_idx(groupname, pid)
        uidx = self._get_user_idx(membername, pid)

        self._groups[gidx]['users'].remove(membername)
        self._users[uidx]['groups'].remove(groupname)

        return self._groups[gidx]

    # Host methods
    def create_host(self, pid, fqdn):
        """See .Gateway.GatewayClient."""
        self.logger.info("Create host: %s", fqdn)
        self._get_project_idx(pid)
        try:
            self._get_host_idx(fqdn, pid)
        except Err:
            pass
        else:
            raise Err("Host %s exists in project %s" % (fqdn, pid))

        n = {'name': fqdn, 'project': pid,
             'created': DateTime.now(), 'expires': DateTime.now() + 10,
             'ips': [], 'frozen': None, }
        self._hosts.append(n)
        return n

    def delete_host(self, pid, fqdn):
        """See .Gateway.GatewayClient."""
        self.logger.info("Delete host: %s", fqdn)
        self._get_project_idx(pid)
        idx = self._get_host_idx(fqdn, pid)
        # TODO: Clean up ips that belong to this host
        del self._hosts[idx]
        return

    def create_ip(self, pid, fqdn, ipadr, mac=None):
        """See .Gateway.GatewayClient."""
        self.logger.info("Add IP addr for %s: %s", fqdn, ipadr)
        self._get_project_idx(pid)
        self._get_host_idx(fqdn, pid)
        try:
            self._get_ip_idx(fqdn, ipadr, pid)
        except Err:
            pass
        else:
            raise Err("Host %s with ip %s exists in project %s" % (
                fqdn, ipadr, pid))

        n = {'project': pid, 'host': fqdn, 'addr': ipadr, }
        self._hosts.append(n)
        return n

    def delete_ip(self, pid, fqdn, ipadr):
        """See .Gateway.GatewayClient."""
        self.logger.info("Delete IP addr for %s: %s", fqdn, ipadr)
        self._get_project_idx(pid)
        hidx = self._get_host_idx(fqdn, pid)
        iidx = self._get_ip_idx(fqdn, ipadr, pid)

        self._hosts[hidx]['ips'].remove(ipadr)
        del self._ips[iidx]
        return

    # Subnet methods

    def create_subnet(self, pid, netaddr, prefixlen, vlan):
        """See .Gateway.GatewayClient."""
        self.logger.info("Creating subnet for %s: %s/%s, vlan: %s",
                         pid, netaddr, prefixlen, vlan)
        self._get_project_idx(pid)
        self._get_vlan_idx(vlan)
        try:
            self._get_subnet_idx(netaddr, prefixlen, vlan, pid)
        except Err:
            pass
        else:
            raise Err("Subnet %s/%s (vlan=%s) exists in project %s" % (
                netaddr, prefixlen, vlan, pid))

        n = {'project': pid, 'prefixlen': prefixlen,
             'netaddr': netaddr, 'vlantag': vlan, 'created': DateTime.now(), }
        self._subnets.append(n)
        return n

    def delete_subnet(self, pid, netaddr, prefixlen, vlan):
        """See .Gateway.GatewayClient."""
        self.logger.info("Delete subnet for %s: %s", pid, netaddr)
        self._get_project_idx(pid)
        self._get_vlan_idx(vlan)
        sidx = self._get_subnet_idx(netaddr, prefixlen, vlan, pid)
        del self._subnets[sidx]
        return {}

    # VLAN methods
    def create_vlan(self, vlan):
        """See .Gateway.GatewayClient."""
        self.logger.info("Creating VLAN %s", vlan)
        try:
            self._get_vlan_idx(vlan)
        except Err:
            pass
        else:
            raise Err("VLAN %s exists" % vlan)

        n = {'vlantag': vlan, 'created': DateTime.now(), }
        self._vlans.append(n)
        return n

    def delete_vlan(self, vlan):
        """See .Gateway.GatewayClient."""
        self.logger.info("Delete VLAN %s", vlan)
        idx = self._get_vlan_idx(vlan)
        # TODO: Remove subnets?
        del self._vlans[idx]
        return {}

    def setup_demo_values(self):
        """Initialize cache with mock data."""
        _created = DateTime.now() - 10
        _expires = DateTime.now() + 10

        self._projects = [{'name': 'p01', 'frozen': None,
                           'expires': _expires,
                           'created': _created, },
                          {'name': 'p02', 'frozen': None,
                           'expires': _expires,
                           'created': _created, }, ]

        self._users = [{'username': 'p01-foo', 'created': _created,
                        'frozen': None, 'expires': _expires,
                        'project': 'p01', 'groups': ['p01-group', ],
                        'otpkey': {'project': 'p01', 'user': 'p01-foo',
                                    'otpuri': 'otpauth://localhost',
                                    'created': _created, }},
                       {'username': 'p01-bar', 'created': _created,
                        'frozen': None, 'expires': _expires,
                        'project': 'p01', 'groups': ['p01-group', ],
                        'otpkey': {'project': 'p01', 'user': 'p01-bar',
                                   'otpuri': 'otpauth://localhost',
                                   'created': _created, }},
                       {'username': 'p02-foo', 'created': _created,
                        'frozen': None, 'expires': _expires,
                        'project': 'p01', 'groups': ['p02-group', ],
                        'otpkey': {'project': 'p02', 'user': 'p02-foo',
                                   'otpuri': 'otpauth://localhost',
                                   'created': _created, }}, ]

        self._groups = [{'project': 'p01', 'groupname': 'p01-group',
                         'users': ['p01-foo', 'p01-bar'],
                         'created': _created, },
                        {'project': 'p02', 'groupname': 'p02-group',
                         'users': ['p02-foo', ],
                         'created': _created, }, ]

        self._hosts = [{'name': 'p01-foo-l.tsd.usit.no', 'project': 'p01',
                        'created': _created, 'expires': _expires,
                        'ips': ['2001:0700:0111:0001:0000:0000:0000:0001',
                                '2001:0700:0111:0001:0000:0000:0000:0002',
                                '2001:0700:0111:0001:0000:0000:0000:0003', ],
                        'frozen': None, },
                       {'name': 'p02-foo-l.tsd.usit.no', 'project': 'p01',
                        'created': _created, 'expires': _expires,
                        'ips': ['10.2.1.1',
                                '2001:0700:0111:0002:0000:0000:0000:0001', ],
                        'frozen': None, }, ]

        self._subnets = [{'project': 'p01', 'prefixlen': 16,
                          'netaddr': '10.1.0.0',
                          'vlantag': 2611, 'created': _created, },
                         {'project': 'p01', 'prefixlen': 64,
                          'netaddr': '2001:0700:0111:0001:0000:0000:0000:0000',
                          'vlantag': 2611, 'created': _created, },
                         {'project': 'p02', 'prefixlen': 16,
                          'netaddr': '10.2.0.0',
                          'vlantag': 2612, 'created': _created, },
                         {'project': 'p02', 'prefixlen': 64,
                          'netaddr': '2001:0700:0111:0002:0000:0000:0000:0000',
                          'vlantag': 2612, 'created': _created, }, ]

        self._ips = [{'project': 'p01', 'host': 'p01-foo-l.tsd.usit.no',
                      'addr': '2001:0700:0111:0001:0000:0000:0000:0001'},
                     {'project': 'p02', 'host': 'p02-foo-l.tsd.usit.no',
                      'addr': '2001:0700:0111:0002:0000:0000:0000:0001'}, ]

        self._vlans = [{'vlantag': 2611, 'created': _created, },
                       {'vlantag': 2612, 'created': _created, }, ]
