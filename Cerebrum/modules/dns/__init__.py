# -*- coding: utf-8 -*-
import cereconf


__version__ = "1.5"

IP_NUMBER = 'IPNumber'
IPv6_NUMBER = 'IPv6Number'
DNS_OWNER='DnsOwner'
REV_IP_NUMBER = 'IPNumber_rev'
A_RECORD = 'ARecord'
AAAA_RECORD = 'AAAARecord'
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
