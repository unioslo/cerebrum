#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2005-2018 University of Oslo, Norway
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

import struct
import socket

from Cerebrum.modules.dns.Errors import DNSError
from Cerebrum.modules.bofhd.errors import CerebrumError


class IPCalc(object):
    """Methods for playing with IP-numbers"""

    @staticmethod
    def netmask_to_intrep(netmask):
        return pow(2, 32) - pow(2, 32 - netmask)

    @staticmethod
    def netmask_to_ip(netmask):
        return IPCalc.long_to_ip(IPCalc.netmask_to_intrep(netmask))

    @staticmethod
    def ip_to_long(ip):
        try:
            return struct.unpack('!L', socket.inet_aton(ip))[0]
        except socket.error, msg:
            raise DNSError("Bad IP: %s" % msg)

    @staticmethod
    def long_to_ip(n):
        return socket.inet_ntoa(struct.pack('!L', n))

    def ip_range_by_netmask(self, subnet, netmask):
        tmp = struct.unpack('!L', socket.inet_aton(subnet))[0]
        start = tmp & IPCalc.netmask_to_intrep(netmask)
        stop = tmp | (pow(2, 32) - 1 - IPCalc.netmask_to_intrep(netmask))
        return start, stop


class IPUtils(object):
    """Methods for verifying (etc.) IP numbers"""

    @staticmethod
    def same_subnet(s1, s2):
        from Cerebrum.Utils import Factory
        from Cerebrum.modules.dns.Errors import SubnetError
        from Cerebrum.modules.dns.Subnet import Subnet
        db = Factory.get('Database')()
        sub = Subnet(db)
        try:
            sub.find(s1)
            tmp = sub.subnet_ip
            sub.clear()
            sub.find(s2)
        except SubnetError:
            return False

        if tmp == sub.subnet_ip:
            return True
        else:
            return False

    @staticmethod
    def in_subnet(ip):
        from Cerebrum.Utils import Factory
        from Cerebrum.modules.dns.Errors import SubnetError
        from Cerebrum.modules.dns.Subnet import Subnet
        db = Factory.get('Database')()
        sub = Subnet(db)
        try:
            sub.find(ip)
        except SubnetError:
            return False
        return True

    @staticmethod
    def is_valid_ipv4(ip):
        """
        Checks if a given IP is formatted according to IPv4-specifications.

        Both complete and incomplete IP's are deemed as valid.
        Examples: 10.0.1.0 - valid
                  10.0 - valid

        :param ip: An incomplete or complete IPv4, to be verified
        :type  ip: str

        :returns: The result of validating the given ip.
        :rtype: boolean
        """
        try:
            socket.inet_aton(ip)
            return True
        except Exception:
            return False

    @staticmethod
    def parse_ipv4(ip):
        """
        Checks if an IP has leading zeroes in its parts, which are not handled
        by the DNS-server. Raises an error if this is the case. Assumes that
        ip-param is a valid ip that has passed the is_valid_ipv4 check.

        Examples: 10.0.10.1 - valid
                  10.0.10.01 - invalid
                  10.0.10 - valid
                  10.0.010 - invalid

        :param ip: An incomplete or complete IPv4.
        :type  ip: str

        """
        parts = ip.split('.')
        # Check for leading zeroes.
        if not IPUtils.is_valid_ipv4(ip):
            raise CerebrumError("Invalid IPv4 address: %s" % ip)
        for part in parts:
            if part.startswith('0') and not len(part) == 1:
                raise CerebrumError("Invalid IPv4-address: %s\n"
                                    "IPv4-address or subnet-fields may not "
                                    "contain leading zeroes.\n"
                                    "Valid example: 10.0.0.1\n"
                                    "Invalid example: 10.0.0.01" % ip)
