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
See Cerebrum/default_config.py:LDAP_SUBNETS for configuration.
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
    subnet_re = re.compile(
        r"^\s*SubNetDef\s*\(\s*'([\d.]+)'[\s,]*(\d+)\s*\)[,\s\)\]]*(?:#(.*))?")
    subst_longspace = re.compile(r"\t\s*| \s+").sub
    notes = {}
    for subnet in filter(None, map(subnet_re.match, file(input_file))):
        network, mask, note = subnet.groups()
        cn = "%s/%s" % (network, mask)
        assert cn not in notes, "Duplicate: " + cn
        notes[cn] = note and subst_longspace("  ", note.strip())
    return notes

def write_subnet_ldif():
    notes = read_subnet_notes()
    DN = ldapconf('SUBNETS', 'dn')
    startAttr, endAttr, objectClasses = ldapconf('SUBNETS', 'rangeSchema')
    objectClasses = ('top', 'ipNetwork') + tuple(objectClasses)
    f = ldif_outfile('SUBNETS')
    f.write(container_entry_string('SUBNETS'))
    for subnet in cereconf_dns.all_nets:
        cn = "%s/%d" % (subnet.net, subnet.mask)
        note = notes.pop(cn, None)
        f.write(entry_string("cn=%s,%s" % (cn, DN), {
            'objectClass':     objectClasses,
            'description':     (note and (iso2utf(note),) or ()),
            'ipNetworkNumber': (subnet.net,),
            'ipNetmaskNumber': (netmask_to_ip(subnet.mask),),
            startAttr:         (str(subnet.start),),
            endAttr:           (str(subnet.stop ),)}))
    assert not notes, "Suspicious parse for: " + ", ".join(notes.keys())
    end_ldif_outfile('SUBNETS', f)

if __name__ == '__main__':
    write_subnet_ldif()
