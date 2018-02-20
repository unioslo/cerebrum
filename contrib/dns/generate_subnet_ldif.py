#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008-2018 University of Oslo, Norway
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

"""Write IP subnet information from Cerebrum to an LDIF file.

See Cerebrum/default_config.py:LDAP_SUBNETS for configuration.

See design/ldap/uioIpNetwork.schema for information about the
uioIpAddressRangeStart, uioIpAddressRangeEnd and uioVlanID attributes.
"""

from six import text_type

from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldapconf,
                                        ldif_outfile,
                                        end_ldif_outfile,
                                        entry_string,
                                        container_entry_string)
from Cerebrum.modules.dns.Subnet import Subnet
from Cerebrum.modules.dns.IPUtils import IPCalc

logger = Factory.get_logger('cronjob')


def write_subnet_ldif():
    db = Factory.get('Database')()
    subnet = Subnet(db)

    dn = ldapconf('SUBNETS', 'dn')
    f = ldif_outfile('SUBNETS')
    f.write(container_entry_string('SUBNETS'))
    subnets = subnet.search()
    for row in subnets:
        cn = "{}/{}".format(row['subnet_ip'], row['subnet_mask'])
        desc = row['description']
        entry = {
            'objectClass': ('top', 'ipNetwork', 'uioIpNetwork'),
            'description': (desc and (desc,) or ()),
            'ipNetworkNumber': (row['subnet_ip'],),
            'ipNetmaskNumber': (IPCalc.netmask_to_ip(row['subnet_mask']),),
            'uioIpAddressRangeStart': (text_type(row['ip_min']),),
            'uioIpAddressRangeEnd': (text_type(row['ip_max']),)}
        if row['vlan_number']:
            entry['uioVlanID'] = (text_type(row['vlan_number']),)
        f.write(entry_string("cn={},{}".format(cn, dn), entry))
    end_ldif_outfile('SUBNETS', f)
    logger.info('Wrote %d entries to %s', len(subnets), f.name)


if __name__ == '__main__':
    write_subnet_ldif()
