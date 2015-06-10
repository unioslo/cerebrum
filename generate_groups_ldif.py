#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2007 University of Oslo, Norway
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

# kbj005 2015.02.11: copied from /home/cerebrum/cerebrum/contrib/no/uio

"""
Generate a group tree for LDAP. This tree resides in
"cn=groups,dc=uit,dc=no" for the time being.

The idea is that some groups in Cerebrum will get a spread,
'LDAP_group', and these groups will be exported into this
tree. Members are people('person' objects in Cerebrum) that are known
to generate_org_ldif. The group tree will include only name and
possibly description of the group. This script will leave a
pickle-file for OrgLDIFUiTMixin() to include, containing memberships
to groups.

This script take the following arguments:

-h, --help : this message
--picklefile fname : pickle file with group memberships
--ldiffile fname : LDIF file with the group tree
"""

import os, sys
import getopt
import pickle
import cerebrum_path

from Cerebrum.Utils import Factory, SimilarSizeWriter
from Cerebrum.modules.LDIFutils import *

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
group = Factory.get('Group')(db)

mbr2grp = {}
top_dn = ldapconf('GROUP', 'dn')

def dump_ldif(file_handle):
    for row in group.search(spread=co.spread_ldap_group):
        group.clear()
        group.find(int(row['group_id']))
        dn = "cn=%s,%s" % (iso2utf(row['name']), top_dn)
        for mbr in group.search_members(group_id=group.entity_id,
                                        member_type=co.entity_person):
            mbr2grp.setdefault(int(mbr["member_id"]), []).append(dn)
        file_handle.write(entry_string(dn, {
            'objectClass': ("top", "uioUntypedObject"),
            'description': (iso2utf(row['description']),)}))
        
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h', [
            'help', 'ldiffile=', 'picklefile='])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--picklefile',):
            picklefile = val
        elif opt in ('--ldiffile',):
            ldiffile = val
    if not (picklefile and ldiffile) or args:
        usage(1)

    destfile = ldif_outfile('GROUP', ldiffile)
    destfile.write(container_entry_string('GROUP'))
    dump_ldif(destfile)
    tmpfname = picklefile + ".tmp"
    pickle.dump(mbr2grp, open(tmpfname, "w"))
    os.rename(tmpfname, picklefile)
    end_ldif_outfile('GROUP', destfile)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
