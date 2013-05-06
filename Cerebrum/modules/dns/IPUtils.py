# -*- coding: iso-8859-1 -*-
import struct
import socket
from Cerebrum.modules.dns.Errors import DNSError

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

