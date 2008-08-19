#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2008 University of Oslo, Norway
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

Write IP subnet information from /cerebrum/etc/cerebrum/cereconf_dns.py
to an LDIF file, which can then be loaded into LDAP.
"""

import cerebrum_path
import cereconf_dns
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum.modules.LDIFutils import ldapconf, iso2utf, \
     ldif_outfile, end_ldif_outfile, entry_string, container_entry_string
netmask_to_ip = IPCalc().netmask_to_ip

# Read the cereconf_dns.py file, looking for Python comments to include
# in LDAP subnet descriptions.  Yuck.
# TODO: Change Cerebrum.modules.dns.SubNetDef so we can get rid of this.
def read_subnet_notes():
    import re
    input_file = re.sub(r'\.py\w$', '.py', cereconf_dns.__file__)
    subnet_match = re.compile(
        r'''^\s*SubNetDef\(\s*'([\d.]+)',\s*(\d+)\),?\s*\#\s*(\S.*)''').match
    unspace = re.compile(r'(?:\t| \s)\s*').sub
    notes = {}
    for subnet in filter(None, map(subnet_match, file(input_file))):
        network, mask, note = subnet.groups()
        cn = "%s/%s" % (network, mask)
        assert cn not in notes, ("Duplicate:", cn)
        notes[cn] = unspace('  ', note.strip())
    return notes

def write_subnet_ldif():
    notes = read_subnet_notes()
    baseDN = ldapconf('SUBNETS', 'dn')
    f = ldif_outfile('SUBNETS')
    rangeTypes = ldapconf('SUBNETS', 'rangeTypes', None)
    f.write(container_entry_string('SUBNETS'))
    for subnet in cereconf_dns.all_nets:
        cn = "%s/%d" % (subnet.net, subnet.mask)
        entry = {
            'objectClass': ('top', 'ipNetwork', 'uioIpNetwork'),
            'ipNetworkNumber': (subnet.net,),
            'ipNetmaskNumber': (netmask_to_ip(subnet.mask),)}
        if rangeTypes:
            # Configurable since there are no attrs for these in RFC 2307.
            entry[rangeTypes[0]] = (str(subnet.start),)
            entry[rangeTypes[1]] = (str(subnet.stop),)
        if cn in notes:
            entry['description'] = (iso2utf(notes.pop(cn)),)
        f.write(entry_string("cn=%s,%s" % (cn, baseDN), entry))
    assert not notes, ("Suspicious parse for:", sorted(notes.keys()))
    end_ldif_outfile('SUBNETS', f)

if __name__ == '__main__':
    write_subnet_ldif()
