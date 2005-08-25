# -*- coding: iso-8859-1 -*-
import struct
import socket

class IPCalc(object):
    """Methods for playing with IP-numbers"""

    def netmask_to_intrep(netmask):
        return pow(2L, 32) - pow(2L, 32-netmask)
    netmask_to_intrep = staticmethod(netmask_to_intrep)

    def ip_to_long(ip):
        return struct.unpack('!L', socket.inet_aton(ip))[0]
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

# arch-tag: b6968cee-155f-11da-9d2c-cbda6ba4b016
