# -*- coding: utf-8 -*-
import struct
import socket
from Cerebrum.modules.dns.Errors import DNSError
from Cerebrum.modules.bofhd.errors import CerebrumError
class IPCalc(object):
    """Methods for playing with IP-numbers"""

    def netmask_to_intrep(netmask):
        return pow(2L, 32) - pow(2L, 32-netmask)
    netmask_to_intrep = staticmethod(netmask_to_intrep)

    def netmask_to_ip(netmask):
        return IPCalc.long_to_ip(IPCalc.netmask_to_intrep(netmask))
    netmask_to_ip = staticmethod(netmask_to_ip)

    def ip_to_long(ip):
        try:
            return struct.unpack('!L', socket.inet_aton(ip))[0]
        except socket.error, msg:
            raise DNSError("Bad IP: %s" % msg)
    ip_to_long = staticmethod(ip_to_long)

    def long_to_ip(n):
        return socket.inet_ntoa(struct.pack('!L', n))
    long_to_ip = staticmethod(long_to_ip)

    def _parse_netdef(self, fname):
        f = file(fname)
        ip_re = re.compile(r'\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+')
        self.subnets = {}
        for line in f.readlines():
            match = ip_re.search(line)
            if match:
                net, mask = match.group(1), int(match.group(2))
                self.subnets[net] = (mask, ) + \
                                    self.ip_range_by_netmask(net, mask)

    def ip_range_by_netmask(self, subnet, netmask):
        tmp = struct.unpack('!L', socket.inet_aton(subnet))[0]
        start = tmp & IPCalc.netmask_to_intrep(netmask)
        stop  =  tmp | (pow(2L, 32) - 1 - IPCalc.netmask_to_intrep(netmask))
        return start, stop

class IPUtils(object):
    """Methods for verifying (etc.) IP numbers"""

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
    same_subnet = staticmethod(same_subnet)
    
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
    in_subnet = staticmethod(in_subnet)

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
        except:
            return False
    is_valid_ipv4 = staticmethod(is_valid_ipv4)

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
    parse_ipv4 = staticmethod(parse_ipv4)
