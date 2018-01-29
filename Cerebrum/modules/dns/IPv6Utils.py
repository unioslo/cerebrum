# -*- coding: utf-8 -*-
import struct
import socket
from Cerebrum.modules.dns.Errors import DNSError

class IPv6Calc(object):
    """Methods for playing with IPv6 numbers
    
    Some of the method names might be poorly chosen. They are chosen to look like
    the similar functions for IPv4.
    """

    def ip_to_long(ip):
        """Convert an IPv6 IP address to long format."""
        try:
            hi, lo = struct.unpack('!QQ', socket.inet_pton(socket.AF_INET6, ip))
        except socket.error, msg:
            raise DNSError("Bad IP: %s" % msg)
        return (hi << 64) | lo
    ip_to_long = staticmethod(ip_to_long)

    def long_to_ip(l):
        """Convert a long or int to an IPv6 address."""
        hi = l >> 64
        lo = l & int('1'*64, 2)
        t = struct.pack('!QQ', hi, lo)
        return socket.inet_ntop(socket.AF_INET6, t)
    long_to_ip = staticmethod(long_to_ip)

    def netmask_to_intrep(netmask):
        return pow(2L, 128) - pow(2L, 128-netmask)
    netmask_to_intrep = staticmethod(netmask_to_intrep)
    
    def netmask_to_ip(netmask):
        return IPv6Calc.long_to_ip(IPv6Calc.netmask_to_intrep(netmask))
    netmask_to_ip = staticmethod(netmask_to_ip)

    def ip_range_by_netmask(subnet, netmask):
        hi, lo = struct.unpack('!QQ', socket.inet_pton(socket.AF_INET6, subnet))
        tmp = hi << 64 | lo
        start = tmp & IPv6Calc.netmask_to_intrep(netmask)
        stop  =  tmp | (pow(2L, 128) - 1 - IPv6Calc.netmask_to_intrep(netmask))
        return start, stop
    ip_range_by_netmask = staticmethod(ip_range_by_netmask)


class IPv6Utils(object):
    """Methods for verifying (etc.) IPv6 numbers"""

    def is_valid_ipv6(ip):
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except:
            return False
    is_valid_ipv6 = staticmethod(is_valid_ipv6)

    def compress(ip):
        t = socket.inet_pton(socket.AF_INET6, ip)
        return socket.inet_ntop(socket.AF_INET6, t)
    compress = staticmethod(compress)

    def explode(aaaa_ip):
        # We check if the address is valid:
        try:
            tmp = socket.inet_pton(socket.AF_INET6, aaaa_ip)
        except socket.error:
            raise DNSError, 'Invalid IPv6 address'

        # Unpack so we get the high and low portions as an int
        hi, lo = struct.unpack('!QQ', tmp)
        # Combine hi and low, and convert to hex-string
        hex_str = '%032x' % (hi << 64 | lo)
        # Put in the colons and return
        return ':'.join([hex_str[x:x+4] for x in range(0, 32, 4)])
    explode = staticmethod(explode)

    def same_subnet(s1, s2):
        from Cerebrum.Utils import Factory
        from Cerebrum.modules.dns.Errors import SubnetError
        from Cerebrum.modules.dns.IPv6Subnet import IPv6Subnet
        db = Factory.get('Database')()
        sub = IPv6Subnet(db)
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
        from Cerebrum.modules.dns.IPv6Subnet import IPv6Subnet
        db = Factory.get('Database')()
        sub = IPv6Subnet(db)
        try:
            sub.find(ip)
        except SubnetError:
            return False
        return True
    in_subnet = staticmethod(in_subnet)

