#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2007-2018 University of Oslo, Norway
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

""" Generate a group tree for LDAP.

This script takes the following arguments:

-h, --help : this message
--picklefile fname : pickle file with group memberships
--ldiffile fname : LDIF file with the group tree
"""

from __future__ import unicode_literals

import getopt
import os
import sys
import cPickle as pickle

from collections import defaultdict

from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldapconf,
                                        entry_string,
                                        ldif_outfile,
                                        end_ldif_outfile,
                                        container_entry_string)

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
co = Factory.get('Constants')(db)
group = Factory.get('Group')(db)

mbr2grp = defaultdict(list)
top_dn = ldapconf('GROUP', 'dn')


def dump_ldif(file_handle):
    group2dn = {}
    for row in group.search(spread=co.spread_ldap_group):
        dn = ("cn={},{}".format(row['name'], top_dn))
        group2dn[row['group_id']] = dn
        file_handle.write(entry_string(dn, {
            'objectClass': ("top", "hiofGroup"),
            'description': (row['description'],),
        }))
    for mbr in group.search_members(spread=co.spread_ldap_group,
                                    member_type=(co.entity_person,
                                                 co.entity_account)):
        if mbr['member_type'] == co.entity_person:
            mbr2grp[int(mbr["member_id"])].append(group2dn[mbr['group_id']])
        elif mbr['member_type'] == co.entity_account:
            ac.clear()
            ac.find(mbr['member_id'])
            if ac.owner_type != co.entity_person:
                continue
            mbr2grp[int(ac.owner_id)].append(group2dn[mbr['group_id']])


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
    end_ldif_outfile('GROUP', destfile)
    tmpfname = picklefile + '.tmp'
    pickle.dump(mbr2grp, open(tmpfname, 'wb'), pickle.HIGHEST_PROTOCOL)
    os.rename(tmpfname, picklefile)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
