# -*- coding: iso-8859-1 -*-
from Cerebrum.modules.dns.IPUtils import IPCalc

class SubNetDef(object):
    def __init__(self, net, mask, reserve=None):
        """Defines a subnet, and defines 'reserved' IPs on the net
        either automatically from netmask, or by using the reserve
        argument which should be a list"""

        self.net = net
        self.mask = mask
        self.__reserve = reserve
        self.reserved = self._calc_reserved(reserve)
        ic = IPCalc()
        self.start, self.stop = ic.ip_range_by_netmask(self.net, self.mask)

    def _calc_reserved(self, reserve):
        ic = IPCalc()
        if reserve is not None:
            return [ic.ip_to_long(n) for n in reserve]
        start, stop = ic.ip_range_by_netmask(self.net, self.mask)
        if self.mask < 22:
            raise ValueError, "Minimum netmask is 22"
        if self.mask == 22:
            return range(start, start+10) + [start+255, start+256] + \
                   [start+255*2+1, start+255*2+2] + [stop]
        elif self.mask == 23:
            return range(start, start+10) + range(start+100, start+121) + \
                   [start+255, start+256] +  [stop]
        elif self.mask == 24:
            return range(start, start+10) + range(start+100, start+121) + \
                   [stop]
        elif self.mask == 25:
            return range(start, start+8) + [stop]
        elif self.mask == 26:
            return range(start, start+8) + [stop]
        elif self.mask == 27:
            return range(start, start+4) + [stop]
        elif self.mask == 28:
            return range(start, start+4) + [stop]
        elif self.mask >= 29:  # entire net is reserved for such small nets
            return range(start, stop+1)

IP_NUMBER = 'IPNumber'
DNS_OWNER='DnsOwner'
REV_IP_NUMBER = 'IPNumber_rev'
A_RECORD = 'ARecord'
HOST_INFO = 'HostInfo'
MX_SET = 'MXSet'
SRV_TARGET = "SRV_target"
SRV_OWNER = "SRV_owner"
GENERAL_DNS_RECORD = "GeneralDnsRecord"
CNAME_OWNER = "Cname_owner"
CNAME_TARGET = "Cname_target"

# TODO: This value should not be hardcoded here.  Didn't put it in
# cereconf as the zone support for dns_owner should be here "real soon
# now"
ZONE='uio.no'

# arch-tag: c2b9ba23-5744-42d6-9a30-28948fff5a49
