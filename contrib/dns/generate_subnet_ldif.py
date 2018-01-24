#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008-2010 University of Oslo, Norway
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

"""Usage: generate_subnet_ldif.py [--logger-name=console ...]

Write IP subnet information from Cerebrum
to an LDIF file, which can then be loaded into LDAP.
See Cerebrum/default_config.py:LDAP_SUBNETS for configuration.

See design/ldap/uioIpNetwork.schema for information about the
uioIpAddressRangeStart, uioIpAddressRangeEnd and uioVlanID
attributes.
"""

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import ldapconf, iso2utf, \
     ldif_outfile, end_ldif_outfile, entry_string, container_entry_string
from Cerebrum.modules.dns.Subnet  import Subnet
from Cerebrum.modules.dns.IPUtils import IPCalc

netmask_to_ip = IPCalc().netmask_to_ip

def write_subnet_ldif():
    DN = ldapconf('SUBNETS', 'dn')
    objectClasses = ('top', 'ipNetwork', 'uioIpNetwork')
    db = Factory.get('Database')()
    f  = ldif_outfile('SUBNETS')
    f.write(container_entry_string('SUBNETS'))
    for row in Subnet(db).search():
        cn   = "%s/%s" % (row['subnet_ip'], row['subnet_mask'])
        desc = row['description']
        entry = {
            'objectClass':     objectClasses,
            'description':     (desc and (iso2utf(desc),) or ()),
            'ipNetworkNumber': (row['subnet_ip'],),
            'ipNetmaskNumber': (netmask_to_ip(row['subnet_mask']),),
            'uioIpAddressRangeStart': (str(int(row['ip_min'])),),
            'uioIpAddressRangeEnd': (str(int(row['ip_max'])),)}
        if row['vlan_number']:
            entry['uioVlanID'] = (str(int(row['vlan_number'])),)
        f.write(entry_string("cn=%s,%s" % (cn, DN), entry))
    end_ldif_outfile('SUBNETS', f)

if __name__ == '__main__':
    write_subnet_ldif()
