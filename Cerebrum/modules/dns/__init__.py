# -*- coding: utf-8 -*-
#
# Copyright 2005-2022 University of Oslo, Norway
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
# Inc., 59 Temple Place, Suite. 330, Boston, MA 02111-1307, USA.
""" DNS module. """
__version__ = "1.5"

IP_NUMBER = 'IPNumber'
IPv6_NUMBER = 'IPv6Number'
DNS_OWNER = 'DnsOwner'
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
ZONE = 'uio.no'
