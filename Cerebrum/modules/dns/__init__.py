# -*- coding: iso-8859-1 -*-
import cereconf

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
        """reserved ips are defined in cereconf as a list of numbers
        relative to the first ip on the net """
        ic = IPCalc()
        if reserve is not None:
            return [ic.ip_to_long(n) for n in reserve]
        start, stop = ic.ip_range_by_netmask(self.net, self.mask)
        by_mask = cereconf.DEFAULT_RESERVED_IP_BY_NETMASK
        if self.mask < min(by_mask):
            raise ValueError, "Minimum netmask is %i" % min(by_mask)
        tmp_mask = self.mask
        if tmp_mask > max(by_mask):
            tmp_mask = max(by_mask)
        return [n+start for n in by_mask[tmp_mask]]

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
