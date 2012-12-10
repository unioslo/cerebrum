# -*- coding: iso-8859-1 -*-
import struct
import socket

class IPv6Calc(object):
    """Methods for playing with IPv6 numbers"""

    def ip_to_long(ip):
        hi, lo = struct.unpack('!QQ', socket.inet_pton(socket.AF_INET6, ip))
        return (hi << 64) | lo
    ip_to_long = staticmethod(ip_to_long)
